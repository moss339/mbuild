# moss-build

MOSS 通用构建系统 - Python CLI 工具

## 新设计原则

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

- **moss.yaml** - 只声明要构建哪些组件（name + path/repository）
- **build_options.yaml** - 全局 C++标准/flags/宏定义（组件继承）
- **component.yaml** - 组件自己管理：依赖谁、怎么构建、怎么安装

## 安装

```bash
pip install -e .
# 或
pip install moss-build
```

## 快速开始

```bash
cd /path/to/moss/project

# 验证配置
moss-build validate -c moss.yaml

# 列出组件及依赖
moss-build list -c moss.yaml

# 同步源码（远程组件）
moss-build sync -c moss.yaml

# 构建全部
moss-build build -c moss.yaml -j 8

# 安装到 dist/
moss-build install -c moss.yaml

# 查看依赖关系
moss-build deps -c moss.yaml

# 查看构建树
moss-build tree -c moss.yaml

# 清理
moss-build clean -c moss.yaml
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
  # inherit: ../../build_options.yaml  # 可选
  type: library

install:
  type: library
  artifacts:
    headers:
      from: include/
      to: include/mcom/
    libraries:
      from: lib/
      patterns:
        - libmcom.a
        - libmcom.so*
```

### 3. 顶层清单 `moss.yaml`

```yaml
name: moss-full
build_options: ./build_options.yaml

components:
  - name: mshm
    path: components/mshm

  - name: mdds
    path: components/mdds

  - name: mcom
    path: components/mcom

  # 远程组件示例
  - name: perception
    repository:
      url: https://github.com/yourorg/perception.git
      branch: main
    path: apps/perception
```

## 命令

| 命令 | 说明 |
|------|------|
| `build` | 按拓扑顺序构建所有组件 |
| `sync` | 同步（克隆/更新）远程组件源码 |
| `install` | 安装到 dist/ |
| `list` | 列出所有组件及依赖 |
| `deps` | 显示依赖关系图 |
| `tree` | 显示组件树 |
| `validate` | 验证配置完整性 |
| `clean` | 清理构建/安装目录 |

## 构建流程

```
moss-build build -c moss.yaml
│
├── 1. 解析配置
│   ├── 读取 moss.yaml
│   ├── 读取 build_options.yaml
│   └── 解析每个组件的 component.yaml
│
├── 2. 同步源码
│   ├── 本地组件 → 直接使用路径
│   └── 远程组件 → git clone/update
│
├── 3. 拓扑排序
│   └── 生成构建顺序
│
├── 4. 并行构建
│   └── cmake + make -j N
│
└── 5. 安装收集
    └── 按 component.yaml 规则安装到 dist/
```

## 目录结构

```
project/
├── moss.yaml
├── build_options.yaml
├── build/                    # 自动生成
│   ├── mshm/
│   ├── mdds/
│   └── mcom/
├── dist/                    # 自动生成
│   ├── bin/
│   ├── lib/
│   ├── include/
│   └── etc/
└── .moss/cache/            # 克隆的源码
    └── perception/
```

## 示例项目

参考 `examples/` 目录下的完整示例。

## License

MIT
