#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qoder Token 用量插件 — 自动打包脚本

功能：
1. 清理临时文件（.DS_Store / __pycache__ / .pyc）
2. 读取 plugin.json 获取版本号
3. 打包为 zip（排除 .git / .preview / .local / dist 等目录）
4. 自动验证打包结果
5. 输出到 dist/token-usage-<version>.zip

用法：
  python3 scripts/package.py          # 打包当前版本
  python3 scripts/package.py --open   # 打包后打开 dist 目录
"""
import argparse
import json
import os
import subprocess
import sys
import zipfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# 从 scripts/ 向上两级到插件根目录（skills/token-usage/scripts -> 插件根）
PLUGIN_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "..", ".."))
DIST_DIR = os.path.join(PLUGIN_ROOT, "dist")

# 打包时排除的目录和文件
EXCLUDE_DIRS = {".git", ".preview", ".local", "dist", ".qoder", "__pycache__"}
EXCLUDE_FILES = {".DS_Store", "*.pyc", ".pricing-update-state.json"}
EXCLUDE_PATTERNS = {"*.bak-*"}  # 备份文件


def should_exclude(path, name):
    """判断路径是否应被排除。"""
    # 排除目录
    for d in EXCLUDE_DIRS:
        if d in path.split(os.sep):
            return True
    # 排除文件
    if name in EXCLUDE_FILES:
        return True
    # 排除模式
    for pat in EXCLUDE_PATTERNS:
        if pat.startswith("*"):
            if name.endswith(pat[1:]):
                return True
        elif pat in name:
            return True
    return False


def clean_temp_files():
    """清理临时文件。"""
    cleaned = 0
    for root, dirs, files in os.walk(PLUGIN_ROOT):
        # 跳过排除目录
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in files:
            if f == ".DS_Store" or f.endswith(".pyc"):
                try:
                    os.remove(os.path.join(root, f))
                    cleaned += 1
                except OSError:
                    pass
    return cleaned


def get_version():
    """从 plugin.json 读取版本号。"""
    manifest = os.path.join(PLUGIN_ROOT, ".qoder-plugin", "plugin.json")
    with open(manifest, encoding="utf-8") as f:
        return json.load(f)["version"]


def package(version):
    """打包插件为 zip。"""
    os.makedirs(DIST_DIR, exist_ok=True)
    out_path = os.path.join(DIST_DIR, f"token-usage-{version}.zip")

    # 删除旧包
    if os.path.exists(out_path):
        os.remove(out_path)

    file_count = 0
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(PLUGIN_ROOT):
            # 过滤目录
            dirs[:] = [d for d in dirs if not should_exclude(root, d)]
            for f in files:
                if should_exclude(root, f):
                    continue
                full = os.path.join(root, f)
                rel = os.path.relpath(full, PLUGIN_ROOT)
                zf.write(full, rel)
                file_count += 1

    return out_path, file_count


def validate(zip_path):
    """验证打包结果。"""
    validator = os.path.expanduser(
        "~/.qoder/plugins/cache/qoder-bundler/qoder-create-plugin/skills/create-plugin/scripts/validate_qoder_plugin.py"
    )
    if not os.path.exists(validator):
        return None, "验证器未找到，跳过验证"

    result = subprocess.run(
        [sys.executable, validator, zip_path],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0, result.stdout + result.stderr


def main():
    p = argparse.ArgumentParser(description="Qoder Token 插件自动打包")
    p.add_argument("--open", action="store_true", help="打包后打开 dist 目录")
    args = p.parse_args()

    print("== Qoder Token 插件打包 ==")

    # 1. 清理
    cleaned = clean_temp_files()
    if cleaned:
        print(f"清理临时文件：{cleaned} 个")

    # 2. 获取版本
    version = get_version()
    print(f"插件版本：{version}")

    # 3. 打包
    zip_path, file_count = package(version)
    size = os.path.getsize(zip_path)
    print(f"打包完成：{zip_path}")
    print(f"  文件数：{file_count} 个")
    print(f"  包大小：{size / 1024:.1f} KB")

    # 4. 验证
    ok, msg = validate(zip_path)
    if ok is True:
        print("  结构校验：通过")
    elif ok is False:
        print(f"  结构校验：失败\n{msg}")
        sys.exit(1)
    else:
        print(f"  结构校验：{msg}")

    # 5. 打开目录
    if args.open:
        subprocess.run(["open", DIST_DIR])

    print("\n打包成功！")


if __name__ == "__main__":
    main()
