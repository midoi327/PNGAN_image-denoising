import numpy as np
import os
import argparse
from tqdm import tqdm

import torch.nn as nn
import torch
from torch.utils.data import DataLoader
import torch.nn.functional as F

import scipy.io as sio
from networks.MIRNet_model import MIRNet
from networks.MPRNet import MPRNet
from networks.RIDNet.ridnet import RIDNET

from dataloaders.data_rgb import get_validation_data_real
import utils
from skimage import img_as_ubyte

import glob


parser = argparse.ArgumentParser(description='noise_removal')

## --------------- input dir ----------------------------

# parser.add_argument('--input_dir', default='./datasets/SIDD/',
#     type=str, help='Directory of validation images')

# parser.add_argument('--input_dir', default='./datasets/Nam/',
#     type=str, help='Directory of validation images')

parser.add_argument('--input_dir', default='./datasets/PolyU/',
    type=str, help='Directory of validation images')


# --------------------- selected method -----------------------

parser.add_argument('--method', default='no_model',
    type=str, help='Model for testing')




# ----------------------- output dir ---------------------------

# parser.add_argument('--result_dir', default='./results/SIDD/noise_removal/',
#     type=str, help='Directory for results')
# parser.add_argument('--result_dir', default='./results/Nam/noise_removal/',
#     type=str, help='Directory for results')
parser.add_argument('--result_dir', default='./results/PolyU/noise_removal/',
    type=str, help='Directory for results')




# ------------------------ weights dir ----------------------------

# parser.add_argument('--weights', default='./checkpoints_MIRNet/model_best.pth',
#     type=str, help='Path to weights')
# parser.add_argument('--weights', default='/data/hxw/MIRNet_Codes/checkpoints_RIDNet_Nam/Denoising/models/RIDNet/model_best.pth',
#     type=str, help='Path to weights')
parser.add_argument('--weights', default='./pre-trained/MIRNet_polyu.pth',
    type=str, help='Path to weights')
# parser.add_argument('--weights', default='/data/hxw/MIRNet_Codes/checkpoints_finetune_MIRNet_official/Denoising/models/MIRNet/model_best.pth',
#     type=str, help='Path to weights')


parser.add_argument('--gpus', default='0', type=str, help='CUDA_VISIBLE_DEVICES')
parser.add_argument('--bs', default=1, type=int, help='Batch size for dataloader')
parser.add_argument('--save_images', default=1, action='store_true', help='Save denoised images in result directory')

args = parser.parse_args()


os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
os.environ["CUDA_VISIBLE_DEVICES"] = "1"

utils.mkdir(args.result_dir)


test_dataset = get_validation_data_real(args.input_dir)
test_loader = DataLoader(dataset=test_dataset, batch_size=args.bs, shuffle=False, num_workers=12, drop_last=False)



# model_restoration = SIMNet()
if args.method == 'mirnet':
    model_restoration = MIRNet()

if args.method == 'ridnet':
    model_restoration = RIDNET()
# model_restoration = RIDNET()

utils.load_checkpoint(model_restoration,args.weights)
print("===>Testing using weights: ", args.weights)

model_restoration.cuda()

model_restoration=nn.DataParallel(model_restoration)

model_restoration.eval()





niqe_test_before = 0 # 노이즈 제거 전 데이터셋 NIQE 평균 점수
niqe_test_after = 0 # 노이즈 제거 후 데이터셋 NIQE 평균 점수
    
    
    


with torch.no_grad():
    psnr_val_rgb = []
    ssim_val_rgb = []
    for ii, data_test in enumerate(tqdm(test_loader), 0):
        rgb_gt = data_test[0].cuda()
        rgb_noisy = data_test[1].cuda()
        filenames = data_test[2]
        rgb_restored = model_restoration(rgb_noisy)
        # rgb_restored = rgb_restored[0] # for MPRNet
        rgb_restored = torch.clamp(rgb_restored,0,1)
     
        psnr_val_rgb.append(utils.batch_PSNR(rgb_restored, rgb_gt, 1.))
        ssim_val_rgb.append(utils.batch_SSIM(rgb_restored, rgb_gt))
        

        rgb_gt = rgb_gt.permute(0, 2, 3, 1).cpu().detach().numpy()
        rgb_noisy = rgb_noisy.permute(0, 2, 3, 1).cpu().detach().numpy()
        rgb_restored = rgb_restored.permute(0, 2, 3, 1).cpu().detach().numpy() # (1, 256, 256, 3)
        
        rgb_gt_niqe = rgb_gt.squeeze(0)
        rgb_gt_niqe = (rgb_gt_niqe[:,:,0]*255).astype(np.uint8)
        rgb_noisy_niqe = rgb_noisy.squeeze(0)
        rgb_noisy_niqe = (rgb_noisy_niqe[:,:,0]*255).astype(np.uint8)
        rgb_restored_niqe = rgb_restored.squeeze(0) # (256, 256, 3)
        rgb_restored_niqe = (rgb_restored_niqe[:,:,0]*255).astype(np.uint8) #(256, 256)이고 값이 0~255
        
        niqe_score_before = utils.niqe(rgb_noisy_niqe)
        niqe_score_after = utils.niqe(rgb_restored_niqe)
        niqe_test_before += niqe_score_before
        niqe_test_after += niqe_score_after
        
        print(filenames, '원본 NIQE:', utils.niqe(rgb_gt_niqe))        
        print(f'전 NIQE: {niqe_score_before: .3f}')
        print(f'후 NIQE: {niqe_score_after: .3f}')
        
        if args.save_images:
            for batch in range(len(rgb_gt)):
                denoised_img = img_as_ubyte(rgb_restored[batch])
                utils.save_img(args.result_dir + filenames[batch][:-4] + '.png', denoised_img)
                
                
            
# psnr_val_rgb = sum(psnr_val_rgb)/len(psnr_val_rgb)
# ssim_val_rgb = sum(ssim_val_rgb)/len(ssim_val_rgb)
# print("PSNR: %.2f " %(psnr_val_rgb))
# print("SSIM: %.3f " %(ssim_val_rgb))
print('\n평균 노이즈 제거 전 NIQE 점수 %.3f' %niqe_test_before)
print('평균 노이즈 제거 후 NIQE 점수 %.3f' %niqe_test_after)
