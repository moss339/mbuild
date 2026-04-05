# mbuild

MOSS 通用构建系统 - Python CLI 工具

## 设计原则

```
┌─────────────────────────────────────────────────────────┐
│                    三层配置模型                           │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  moss.yaml              # 顶层清单（只声明组件）          │
│     │                                                      │
│     ├── build_options   # 全局编译选项（引用）            │
│     │                                                      │
│     └── components/*/component.yaml  # 组件自描述       │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**核心原则：组件自描述 + CMake 原生 install**

- `moss.yaml` - 只声明要构建哪些组件（name + path/repository）
- `build_options.yaml` - 全局 C++标准/flags/宏定义（组件继承）
- `component.yaml` - 组件自描述：依赖谁、怎么构建（install 由 CMake 管理）

## 安装

```bash
pip install -e .
# 或
pip install mbuild
```

## 快速开始

```bash
cd /path/to/moss/project

# 验证配置
mbuild validate -c moss.yaml

# 构建全部（并行）
mbuild build -c moss.yaml -j 8

# 安装（使用 CMake 原生 install 规则）
mbuild install -c moss.yaml

# 查看结果
ls dist/
```

## 配置示例

### 1. 全局编译选项 `build_options.yaml`

```yaml
cxx_standard: C++17
cxx_flags:
  - -Wall
  - -Wextra
  - -Wno-unused-parameter
defines:
  - VERSION=1
build_type: Release
parallel_jobs: 8
```

### 2. 组件自描述 `components/mcom/component.yaml`

```yaml
name: mcom
description: MOSS 统一通信中间件

dependencies:
  local:
    - mdds
    - mshm
  system:
    - pthread
    - protobuf

build:
  type: library
  cmake_options:
    MCOM_BUILD_EXAMPLES: OFF
```

**注意**: install 规则在 CMakeLists.txt 中配置，不需要在 YAML 中重复声明。

### 3. 顶层清单 `moss.yaml`

```yaml
name: moss-full
build_options: ./build_options.yaml

settings:
  install_root: ./dist
  cache_dir: .moss/cache

components:
  - name: mshm
    path: components/mshm

  - name: mdds
    path: components/mdds

  - name: mcom
    path: components/mcom
```

## 命令

| 命令 | 说明 |
|------|------|
| `build` | 按拓扑顺序构建所有组件 |
| `sync` | 同步（克隆/更新）远程组件源码 |
| `install` | 使用 CMake 原生规则安装到 dist/ |
| `list` | 列出所有组件及依赖 |
| `deps` | 显示依赖关系图 |
| `tree` | 显示组件树 |
| `validate` | 验证配置完整性 |
| `clean` | 清理构建/安装目录 |

## 构建流程

```
mbuild build -c moss.yaml
│
├── 1. 解析配置
│   ├── 读取 moss.yaml
│   ├── 读取 build_options.yaml
│   └── 解析每个组件的 component.yaml
│
├── 2. 源码同步
│   ├── 本地组件 → 直接使用路径
│   └── 远程组件 → git clone/update
│
├── 3. 拓扑排序依赖
│   └── 生成构建顺序
│
├── 4. 并行构建
│   └── cmake + cmake --build --parallel N
│
└── 5. 安装
    └── cmake --install build/<comp> --prefix dist/<comp>
```

## 安装目录结构

```
dist/
├── mcom/              # 每个组件安装到自己的子目录
│   ├── lib/
│   └── include/
├── mlog/
│   ├── lib/
│   └── include/
├── mshm/
│   ├── lib/
│   └── include/
├── deploy_manifest.yaml
└── ...
```

## 示例项目

参考 `examples/` 目录下的完整示例。

## License

MIT
