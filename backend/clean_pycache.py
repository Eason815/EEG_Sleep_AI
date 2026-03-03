"""
清理 __pycache__ 目录脚本
功能: 查找并删除当前目录及其子目录中的所有 __pycache__ 目录
"""

import os
import sys
import shutil
import time
from pathlib import Path


def find_pycache_directories(start_path):
    """
    递归查找所有 __pycache__ 目录
    
    Args:
        start_path: 起始搜索路径
        
    Returns:
        list: 找到的 __pycache__ 目录路径列表
    """
    pycache_dirs = []
    
    print(f"正在搜索 __pycache__ 目录，起始路径: {start_path}")
    print("-" * 60)
    
    # 使用 os.walk 递归遍历目录
    for root, dirs, files in os.walk(start_path):
        # 检查当前目录是否是 __pycache__
        if os.path.basename(root) == "__pycache__":
            pycache_dirs.append(root)
    
    return pycache_dirs


def display_pycache_directories(pycache_dirs):
    """
    显示找到的 __pycache__ 目录
    
    Args:
        pycache_dirs: __pycache__ 目录列表
    """
    if not pycache_dirs:
        print("未找到任何 __pycache__ 目录！")
        return
    
    print(f"找到 {len(pycache_dirs)} 个 __pycache__ 目录:")
    print("-" * 60)
    
    for i, dir_path in enumerate(pycache_dirs, 1):
        # 计算目录大小
        try:
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(dir_path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    if os.path.isfile(fp):
                        total_size += os.path.getsize(fp)
            
            # 转换为合适的单位
            if total_size < 1024:
                size_str = f"{total_size} B"
            elif total_size < 1024 * 1024:
                size_str = f"{total_size / 1024:.2f} KB"
            else:
                size_str = f"{total_size / (1024 * 1024):.2f} MB"
                
            print(f"{i:3d}. {dir_path} ({size_str})")
        except Exception as e:
            print(f"{i:3d}. {dir_path} (无法计算大小: {e})")
    
    print("-" * 60)
    
    # 计算总大小
    total_all_size = 0
    for dir_path in pycache_dirs:
        try:
            for dirpath, dirnames, filenames in os.walk(dir_path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    if os.path.isfile(fp):
                        total_all_size += os.path.getsize(fp)
        except:
            pass
    
    if total_all_size < 1024 * 1024:
        total_size_str = f"{total_all_size / 1024:.2f} KB"
    else:
        total_size_str = f"{total_all_size / (1024 * 1024):.2f} MB"
    
    print(f"总计: {len(pycache_dirs)} 个目录，约 {total_size_str}")


def delete_pycache_directories(pycache_dirs):
    """
    删除 __pycache__ 目录
    
    Args:
        pycache_dirs: __pycache__ 目录列表
        
    Returns:
        tuple: (成功删除的数量, 失败删除的数量, 失败列表)
    """
    success_count = 0
    fail_count = 0
    failed_dirs = []
    
    print("\n开始删除 __pycache__ 目录...")
    print("-" * 60)
    
    for i, dir_path in enumerate(pycache_dirs, 1):
        try:
            print(f"正在删除 ({i}/{len(pycache_dirs)}): {dir_path}")
            shutil.rmtree(dir_path)
            success_count += 1
            print(f"  ✓ 删除成功")
        except PermissionError:
            print(f"  ✗ 权限不足，无法删除")
            fail_count += 1
            failed_dirs.append((dir_path, "权限不足"))
        except FileNotFoundError:
            print(f"  ✗ 目录不存在（可能已被删除）")
            fail_count += 1
            failed_dirs.append((dir_path, "目录不存在"))
        except Exception as e:
            print(f"  ✗ 删除失败: {e}")
            fail_count += 1
            failed_dirs.append((dir_path, str(e)))
    
    return success_count, fail_count, failed_dirs


def get_user_confirmation():
    """
    获取用户确认
    
    Returns:
        bool: True 表示确认删除，False 表示取消
    """
    print("\n" + "=" * 60)
    print("请确认是否删除以上所有 __pycache__ 目录")
    print("=" * 60)
    
    while True:
        response = input("输入 'yes' 确认删除，输入 'no' 取消操作: ").strip().lower()
        
        if response in ['yes', 'y']:
            return True
        elif response in ['no', 'n']:
            return False
        else:
            print("无效输入，请输入 'yes' 或 'no'")


def main():
    """主函数"""
    print("=" * 60)
    print("        __pycache__ 目录清理工具")
    print("=" * 60)
    
    # 获取脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"脚本位置: {script_dir}")
    print(f"工作目录: {os.getcwd()}")
    print()
    
    # 查找 __pycache__ 目录
    start_time = time.time()
    pycache_dirs = find_pycache_directories(script_dir)
    search_time = time.time() - start_time
    
    # 显示找到的目录
    display_pycache_directories(pycache_dirs)
    
    if not pycache_dirs:
        print("\n没有需要清理的 __pycache__ 目录。")
        input("\n按 Enter 键退出...")
        return
    
    print(f"\n搜索完成，耗时: {search_time:.2f} 秒")
    
    # 获取用户确认
    if not get_user_confirmation():
        print("\n操作已取消。")
        input("\n按 Enter 键退出...")
        return
    
    # 删除目录
    delete_start_time = time.time()
    success_count, fail_count, failed_dirs = delete_pycache_directories(pycache_dirs)
    delete_time = time.time() - delete_start_time
    
    # 显示结果
    print("\n" + "=" * 60)
    print("清理完成！")
    print("=" * 60)
    print(f"成功删除: {success_count} 个目录")
    print(f"删除失败: {fail_count} 个目录")
    print(f"删除耗时: {delete_time:.2f} 秒")
    
    if failed_dirs:
        print("\n失败的目录:")
        for dir_path, error in failed_dirs:
            print(f"  - {dir_path}: {error}")
    
    # 建议
    print("\n" + "-" * 60)
    print("建议:")
    print("1. 可以将此脚本添加到 .gitignore 中")
    print("2. 可以设置定时任务定期清理")
    print("3. 可以在 Python 启动时设置 PYTHONDONTWRITEBYTECODE=1 环境变量")
    print("   来避免生成 __pycache__ 目录")
    print("-" * 60)
    
    input("\n按 Enter 键退出...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n操作中断。")
        sys.exit(1)
    except Exception as e:
        print(f"\n程序发生错误: {e}")
        import traceback
        traceback.print_exc()
        input("\n按 Enter 键退出...")
        sys.exit(1)