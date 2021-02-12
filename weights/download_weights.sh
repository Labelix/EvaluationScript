#!/bin/sh
file="model_final_f10217.pkl"
if [ ! -f $file ]; then
  echo "Downloading $file!"
  wget https://dl.fbaipublicfiles.com/detectron2/COCO-InstanceSegmentation/mask_rcnn_R_50_FPN_3x/137849600/model_final_f10217.pkl
else
  echo "$file already exists!"
fi
