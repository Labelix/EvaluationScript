#!/usr/bin/env python

import argparse
import logging
import os
import glob

import cv2
import numpy as np
import torch
import tqdm

from detectron2.config import get_cfg
from detectron2.data import DatasetCatalog, MetadataCatalog, build_detection_test_loader
from detectron2.data.datasets import register_coco_instances
from detectron2.engine import DefaultTrainer, DefaultPredictor, default_argument_parser, default_setup, hooks, launch
from detectron2.utils import comm
from detectron2.utils.collect_env import collect_env_info
from detectron2.utils.env import seed_all_rng
from detectron2.utils.logger import setup_logger
from detectron2.utils.visualizer import Visualizer, GenericMask
from detectron2.evaluation import (
    CityscapesInstanceEvaluator,
    CityscapesSemSegEvaluator,
    COCOEvaluator,
    COCOPanopticEvaluator,
    DatasetEvaluators,
    LVISEvaluator,
    PascalVOCDetectionEvaluator,
    SemSegEvaluator,
    inference_on_dataset,
    print_csv_format,
)
from fvcore.common.file_io import PathManager


def get_parser():
    parser = argparse.ArgumentParser(
        description="A python script which utilizes detectron2 able to train Neural Networks and Predict labels!")
    parser.add_argument(
        "--num_gpus",
        type=int,
        default=0,
        help="Specifies how many gpus will be used."
    )
    parser.add_argument(
        "--num_machines",
        type=int,
        default=0,
        help="Specifies how many gpus will be used."
    )
    parser.add_argument(
        "--dist_url",
        type=str,
        default="",
        help="Sets the distance url."
    )
    parser.add_argument(
        "--machine_rank",
        type=int,
        default=0,
        help="Specifies the machine rank."
    )
    parser.add_argument(
        "--config-file",
        default="configs/quick_schedules/mask_rcnn_R_50_FPN_inference_acc_test.yaml",
        metavar="FILE",
        help="path to config file",
    )
    parser.add_argument(
        "--input",
        nargs="+",
        help="A list of space separated input images; "
             "or a single glob pattern such as 'directory/*.jpg'",
    )
    parser.add_argument(
        "--output",
        default="./out/checkpoints",
        help="A file or directory to save output visualizations. "
             "If not given, will show output in an OpenCV window.",
    )
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.5,
        help="Minimum score for instance predictions to be shown",
    )
    parser.add_argument(
        "--opts",
        help="Modify config options using the command-line 'KEY VALUE' pairs",
        default=[],
        nargs=argparse.REMAINDER,
    )
    parser.add_argument(
        "--masks_only",
        action='store_true',
        help="Flag to only write masks to output directory.",
    )
    parser.add_argument(
        "--inference_only",
        action='store_true',
        help="Flag to only write inference image to output directory.",
    )
    parser.add_argument(
        "--disable-config-output",
        action='store_true',
        help="Disable config.yaml output.",
    )
    parser.add_argument(
        "--disable-log-output",
        action='store_true',
        help="Disable log.txt output.",
    )
    return parser


def get_paths(in_dir):
    images = []

    progress = tqdm.tqdm(in_dir, "/tmp/out")

    for path in progress:
        progress.set_description(path)
        imgs = glob.glob(path)
        images.extend(imgs)

    logger.info("IMAGES: {}".format(images))

    return images


def draw_polygons(height, width, polygons, output_path):
    img = np.zeros((height, width), dtype='uint8')
    polygons_ = [poly.astype(np.int32).reshape(-1, 2) for poly in polygons]
    cv2.fillPoly(img, polygons_, 255)
    cv2.imwrite(output_path, img)


def setup(args, eval=True):
    """
    Create configs and perform basic setups.
    """
    cfg = get_cfg()
    cfg.merge_from_file(args.config_file)
    cfg.merge_from_list(args.opts)
    cfg.OUTPUT_DIR = args.output

    cfg.MODEL.RETINANET.SCORE_THRESH_TEST = args.confidence_threshold
    cfg.MODEL.ROI_HEADS.SCORE_THRESH_TEST = args.confidence_threshold
    cfg.MODEL.PANOPTIC_FPN.COMBINE.INSTANCES_CONFIDENCE_THRESH = args.confidence_threshold

    # if eval:
    #    cfg.MODEL.WEIGHTS = "../weights/model_final_f10217.pkl"  # os.path.join(cfg.OUTPUT_DIR, "model_final.pth")

    cfg.freeze()
    custom_setup(cfg, args)

    return cfg


def main(args):
    # # register dataset
    # register_coco_instances(name="cause_brain_2019_train", metadata={},
    #                         json_file="./datasets/coco/annotations/instances_train2019.json",
    #                         image_root="./datasets/coco/train2019")
    #
    # register_coco_instances(name="cause_brain_2019_val", metadata={},
    #                         json_file="./datasets/coco/annotations/instances_valid2019.json",
    #                         image_root="./datasets/coco/valid2019")
    #
    # register_coco_instances(name="cause_brain_2019_test", metadata={},
    #                         json_file="./datasets/coco/annotations/instances_test2019.json",
    #                         image_root="./datasets/coco/test2019")

    cfg = setup(args, eval=True)

    # os.makedirs(cfg.OUTPUT_DIR, exist_ok=True)

    # evaluate trained model
    if not args.masks_only and not args.inference_only:
        os.makedirs(os.path.join(cfg.OUTPUT_DIR, "inference"), exist_ok=True)
        os.makedirs(os.path.join(cfg.OUTPUT_DIR, "masks"), exist_ok=True)

    # # COCO OUTPUT:
    #
    # # setup trainer and evaluate
    # trainer = DefaultTrainer(cfg)
    # evaluator = COCOEvaluator(dataset_name="balloon_val", cfg=cfg, distributed=False, output_dir="./output/")
    # val_loader = build_detection_test_loader(cfg, "balloon_val")
    # print(inference_on_dataset(trainer.model, val_loader, evaluator))
    # # another equivalent way is to use trainer.test

    # MASK OUTPUT:

    predictor = DefaultPredictor(cfg)

    # dataset_dicts = DatasetCatalog.get(cfg.DATASETS.TEST[0])
    metadata = MetadataCatalog.get(cfg.DATASETS.TEST[0])
    class_names = metadata.get("thing_classes", None)

    for filename in get_paths(args.input):
        basename = os.path.basename(filename)

        logger.info("Loading: " + filename)
        im = cv2.imread(filename)

        outputs = predictor(im)
        if len(outputs['instances']) > 0:
            if len(outputs['instances']) > 0:
                instances = outputs["instances"].to("cpu")

                scores = instances.scores
                logger.info("Scores" + str(scores))
                classes = instances.pred_classes.numpy()
                # labels = _create_text_labels(classes, scores, metadata.get("thing_classes", None))
                labels = [class_names[i] for i in classes]

                # logger.info("MASKS {}".format(instances.pred_masks))

                try:
                    masks = np.asarray(instances.pred_masks)
                    masks = [GenericMask(x, im.shape[0], im.shape[1]) for x in masks]

                    # print(filename)
                    # print("Masks")
                    # print(labels)
                    for i in range(len(masks)):
                        name, ext = tuple(os.path.splitext(basename))
                        output_filename = name + "_" + labels[i] + ext
                        output_path = os.path.join(cfg.OUTPUT_DIR, "" if args.masks_only else "masks", output_filename)

                        draw_polygons(im.shape[0], im.shape[1], masks[i].polygons, output_path)
                        # for segment in masks[i].polygons:
                        #     print(i, segment.reshape(-1, 2).shape, labels[i])

                    if not args.masks_only:
                        vis = Visualizer(im[:, :, ::-1],
                                         metadata=metadata,
                                         scale=2.0,
                                         )

                        vis = vis.draw_instance_predictions(outputs["instances"].to("cpu"))
                        vis.save(os.path.join(cfg.OUTPUT_DIR, "" if args.inference_only else "inference", basename))
                except AttributeError:
                    logger.error("No segmentation exists!")
            else:
                logger.info('No Instances found!')


def custom_setup(cfg, args):
    """
    Perform some basic common setups at the beginning of a job, including:

    1. Set up the detectron2 logger
    2. Log basic information about environment, cmdline arguments, and config
    3. Backup the config to the output directory

    Args:
        cfg (CfgNode): the full config to be used
        args (argparse.NameSpace): the command line arguments to be logged
    """
    output_dir = cfg.OUTPUT_DIR
    if comm.is_main_process() and output_dir:
        PathManager.mkdirs(output_dir)

    rank = comm.get_rank()

    if args.disable_log_output:
        setup_logger(distributed_rank=rank, name="fvcore")
        logger = setup_logger(distributed_rank=rank)
    else:
        setup_logger(output_dir, distributed_rank=rank, name="fvcore")
        logger = setup_logger(output_dir, distributed_rank=rank)

    logger.info("Rank of current process: {}. World size: {}".format(rank, comm.get_world_size()))
    logger.info("Environment info:\n" + collect_env_info())

    logger.info("Command line arguments: " + str(args))
    if hasattr(args, "config_file") and args.config_file != "":
        logger.info(
            "Contents of args.config_file={}:\n{}".format(
                args.config_file, PathManager.open(args.config_file, "r").read()
            )
        )

    logger.info("Running with full config:\n{}".format(cfg))
    if hasattr(args, "disable-config-output") and args.disable_config_output and comm.is_main_process() and output_dir:
        # Note: some of our scripts may expect the existence of
        # config.yaml in output directory
        path = os.path.join(output_dir, "config.yaml")
        with PathManager.open(path, "w") as f:
            f.write(cfg.dump())
        logger.info("Full config saved to {}".format(path))

    # make sure each worker has a different, yet deterministic seed if specified
    seed_all_rng(None if cfg.SEED < 0 else cfg.SEED + rank)

    # cudnn benchmark has large overhead. It shouldn't be used considering the small size of
    # typical validation set.
    if not (hasattr(args, "eval_only") and args.eval_only):
        torch.backends.cudnn.benchmark = cfg.CUDNN_BENCHMARK


if __name__ == "__main__":
    # mp.set_start_method("spawn", force=True)
    args = get_parser().parse_args()

    logger = logging.getLogger()
    logger.propagate = False
    logger.info("Arguments: " + str(args))

    launch(
        main,
        args.num_gpus,
        num_machines=args.num_machines,
        machine_rank=args.machine_rank,
        dist_url=args.dist_url,
        args=(args,),
    )
