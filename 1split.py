import os
import shutil
import random
import glob  

# 配置路径
data_folder = r'./sleep-edf/data'  # 处理后的数据文件夹
train_folder = os.path.join(data_folder, 'train')
val_folder = os.path.join(data_folder, 'val')
test_folder = os.path.join(data_folder, 'test')

# 清理和创建子文件夹
for folder in [data_folder, train_folder, val_folder, test_folder]:
    if os.path.exists(folder):
        shutil.rmtree(folder)  # 删除旧的（如果存在）
    os.makedirs(folder)


original_folder = r'./sleep-edf/sleep-cassette'
# --- 1. 扫描和匹配 PSG 和 Hypnogram 文件 ---
# 使用 glob 查找所有以 '-PSG.edf' 结尾的 PSG 文件。
psg_files = glob.glob(os.path.join(original_folder, '*-PSG.edf'))
# 使用 glob 查找所有以 '-Hypnogram.edf' 结尾的 Hypnogram 文件。
hyp_files = glob.glob(os.path.join(original_folder, '*-Hypnogram.edf'))

# 构建一个字典来存储每个患者的 PSG 和 Hypnogram 文件路径，确保它们是配对的。
patient_dict = {}
for psg in psg_files:
    # 从文件名中提取患者ID (例如 'SC4001E0-PSG.edf' -> 'SC4001E0')
    # 这里假设患者ID是文件名前6个字符。需要根据实际文件名格式调整。
    patient_id = os.path.basename(psg)[:6] 
    patient_dict[patient_id] = {'psg': psg, 'hyp': None}  # 初始化 Hypnogram 为 None
for hyp in hyp_files:
    patient_id = os.path.basename(hyp)[:6]
    if patient_id in patient_dict:  # 如果找到对应的 PSG 文件，则更新 Hypnogram 路径
        patient_dict[patient_id]['hyp'] = hyp

# 过滤出所有同时拥有 PSG 和 Hypnogram 文件的有效患者。
valid_patients = [(pid, data['psg'], data['hyp']) for pid, data in patient_dict.items() if data['hyp']]

print(f"Total valid patients: {len(valid_patients)}")  # 打印有效患者数

# --- 2. 划分病人列表 ---
random.seed(42)  # 确保可重复
random.shuffle(valid_patients)  # 随机打乱

total = len(valid_patients)
train_split = int(0.8 * total)
val_split = int(0.9 * total)
train_patients = valid_patients[:train_split]
val_patients = valid_patients[train_split:val_split]
test_patients = valid_patients[val_split:]

print(f"Train patients: {len(train_patients)}, Val patients: {len(val_patients)}, Test patients: {len(test_patients)}")

# --- 3. 复制文件到对应文件夹 ---
def copy_patient_files(patient_list, dest_folder):
    for pid, psg_path, hyp_path in patient_list:
        # 复制 PSG 和 Hypnogram 文件
        shutil.copy(psg_path, os.path.join(dest_folder, os.path.basename(psg_path)))
        shutil.copy(hyp_path, os.path.join(dest_folder, os.path.basename(hyp_path)))
        print(f"Copied patient {pid} to {dest_folder}")  # 可选：打印进度

copy_patient_files(train_patients, train_folder)
copy_patient_files(val_patients, val_folder)
copy_patient_files(test_patients, test_folder)

print("Data split complete! Files copied to train, val, test folders under sleep-cassette-processed.")
