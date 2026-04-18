#!/bin/bash
# mbuild 环境设置脚本
# 用法: source setup.sh

# 获取脚本所在目录
MBUILD_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 添加到 PYTHONPATH
export PYTHONPATH="${MBUILD_ROOT}${PYTHONPATH:+:$PYTHONPATH}"

# 创建 mbuild 命令函数
mbuild() {
    python3 -m mbuild "$@"
}

# 导出函数供子 shell 使用
export -f mbuild

# 导出 mbuild 根目录
export MBUILD_ROOT

echo "mbuild 已加载"
echo "  MBUILD_ROOT=${MBUILD_ROOT}"
echo "  用法: mbuild --help"
