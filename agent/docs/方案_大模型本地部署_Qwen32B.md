# 方案一：大模型本地部署方案 (Qwen-32B / 4x RTX 3090)

## 1. 部署目标与环境
*   **目标模型**: Qwen2.5-32B-Instruct (量化版本: GPTQ-Int4 或 AWQ-Int4)
*   **硬件环境**: 4张 NVIDIA GeForce RTX 3090 (每张 24GB VRAM，共 96GB)
*   **操作系统**: Ubuntu 22.04 LTS / Windows WSL2 (推荐 Ubuntu)
*   **显卡驱动**: NVIDIA Driver 535+ / CUDA 12.1+

## 2. 资源评估与策略选择

Qwen-32B-Int4 模型权重约为 **18-20GB**。
单张 3090 (24GB) 理论上可以勉强运行，但在高并发或长上下文（Long Context）场景下容易显存溢出（OOM），且推理速度受限。

针对 4张 3090 的配置，我们推荐以下两种部署策略：

### 策略 A：高性能低延迟模式 (推荐用于 Demo 展示)
*   **配置**: 使用 **Tensor Parallelism (TP) = 2**。
*   **原理**: 将模型切分到 2 张显卡上运行。
*   **优势**: 
    *   **显存充裕**: 48GB 总显存，除去模型权重，剩余约 25GB+ 用于 KV Cache，支持极长上下文（32k+）。
    *   **速度快**: 双卡并行计算，首字延迟（TTFT）和生成速度显著提升。
*   **资源占用**: 占用 2 张显卡，剩余 2 张可用于其他模型（如 Embedding 模型、Rerank 模型）或部署第二套备用服务。

### 策略 B：高吞吐并发模式 (推荐用于多人压测)
*   **配置**: 部署 **两个独立实例**，每个实例使用 TP=2。
*   **原理**: 启动两个 API 服务端口（如 8000 和 8001），前端通过 Nginx 做负载均衡。
*   **优势**: 吞吐量翻倍，可同时支持更多测试人员进行并发测试。
*   **资源占用**: 占用全部 4 张显卡。

## 3. 技术栈选型

推荐使用 **vLLM** 作为推理引擎，它是目前生产环境中最快、最稳定的开源推理框架。

*   **推理引擎**: [vLLM](https://github.com/vllm-project/vllm) (支持连续批处理、PagedAttention，吞吐量极高)
*   **容器化**: Docker + NVIDIA Container Toolkit
*   **接口协议**: OpenAI Compatible API (无缝替换现有 OpenAI/DeepSeek 调用代码)

## 4. 部署实施步骤 (基于 Docker)

### 4.1 环境准备
确保已安装 Docker 和 NVIDIA Container Toolkit。
```bash
# 验证 GPU 可见性
docker run --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

### 4.2 启动服务 (以策略 A：TP=2 为例)

我们将使用 `vllm/vllm-openai` 镜像。

```bash
# 设定模型名称 (HuggingFace ID)
export MODEL_NAME="Qwen/Qwen2.5-32B-Instruct-GPTQ-Int4"

# 启动容器
docker run -d \
  --name vllm-service \
  --runtime nvidia \
  --gpus '"device=0,1"' \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  -p 8000:8000 \
  --ipc=host \
  vllm/vllm-openai:latest \
  --model $MODEL_NAME \
  --tensor-parallel-size 2 \
  --gpu-memory-utilization 0.95 \
  --max-model-len 32768 \
  --trust-remote-code
```

*   `--gpus '"device=0,1"'`: 指定使用前两张卡。
*   `--tensor-parallel-size 2`: 开启 2 卡并行。
*   `--max-model-len`: 限制上下文长度，防止 OOM，根据实际测试情况调整。

### 4.3 接口调用测试

部署完成后，服务将暴露 OpenAI 兼容接口。

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen2.5-32B-Instruct-GPTQ-Int4",
    "messages": [
      {"role": "system", "content": "你是一个智能助手。"},
      {"role": "user", "content": "你好，请介绍一下你自己。"}
    ]
  }'
```

## 5. 备选方案：Ollama (最简部署)

如果服务器环境配置 Docker 困难，可以使用 Ollama 进行裸机部署。

1.  下载 Ollama (Linux/Windows)。
2.  拉取模型: `ollama run qwen2.5:32b-instruct-q4_0`
3.  Ollama 会自动管理 GPU 显存，但并发性能和长文本性能弱于 vLLM。

## 6. 建议

1.  **显存监控**: 部署期间使用 `nvtop` 实时监控显存占用。
2.  **量化选择**: 优先测试 GPTQ-Int4 版本。如果发现推理精度下降明显（Agent 指令遵循能力变弱），可尝试 AWQ 版本或回退到 FP16（此时需 TP=4，占用 4 张卡）。
3.  **API Key**: 本地部署默认无鉴权，如需对外网暴露，务必在 Nginx 层增加 Basic Auth 或 API Key 校验。

