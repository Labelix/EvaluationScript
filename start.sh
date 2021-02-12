#!/bin/sh

output_dir="out"
if [ -d $output_dir ]; then
  rm -rf $output_dir
fi

mkdir $output_dir

base_dir=$(dirname $(realpath "$0"))

echo "$base_dir:/tmp/EVAL"

docker run --rm --shm-size 8gb --gpus 1 \
    -v "$base_dir:/tmp/EVAL" \
    cknoll/detectron2 python /tmp/EVAL/main.py \
    --disable-log-output \
    --disable-config-output \
    --masks_only \
    --config-file ./configs/COCO-InstanceSegmentation/mask_rcnn_R_50_FPN_3x.yaml \
    --input /tmp/EVAL/in/* \
    --output /tmp/EVAL/out \
    --opts MODEL.WEIGHTS "/tmp/EVAL/weights/model_final_f10217.pkl"