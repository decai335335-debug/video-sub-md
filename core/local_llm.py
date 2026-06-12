"""本地大模型推理客户端

默认使用 transformers 加载本地 Qwen3 等模型，支持分析和翻译。
模型在首次调用时懒加载，后续调用复用已加载的模型实例。
"""

import re
import time
from pathlib import Path
from typing import Optional

# 延迟导入 heavy 依赖，只在真正需要时加载
transformers = None
torch = None


class LocalLLMClient:
    """本地 LLM 客户端（单例懒加载）"""

    _instance: Optional["LocalLLMClient"] = None

    def __new__(cls, model_path: str = ""):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, model_path: str = ""):
        if self._initialized or not model_path:
            return
        self.model_path = model_path
        self.tokenizer = None
        self.model = None
        self.device = None
        self._initialized = True

    def _load(self):
        """懒加载模型和分词器。"""
        if self.model is not None and self.tokenizer is not None:
            return

        global transformers, torch
        if transformers is None:
            import transformers as _transformers
            transformers = _transformers
        if torch is None:
            import torch as _torch
            torch = _torch

        path = Path(self.model_path)
        if not path.exists():
            raise RuntimeError(f"本地模型路径不存在: {self.model_path}")

        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            print(f"[本地模型] 检测到 GPU: {gpu_name}")
        else:
            print("[本地模型] 未检测到 GPU，将使用 CPU 运行（速度较慢）")

        print(f"[本地模型] 正在加载 {self.model_path}，首次加载可能需要几十秒...")
        start = time.time()

        self.tokenizer = transformers.AutoTokenizer.from_pretrained(
            self.model_path,
            trust_remote_code=True,
            local_files_only=True,
        )

        # 自动选择精度：有 CUDA 用 bf16/fp16，否则用 fp32 或 int8
        if torch.cuda.is_available():
            dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
            self.model = transformers.AutoModelForCausalLM.from_pretrained(
                self.model_path,
                dtype=dtype,
                device_map="auto",
                trust_remote_code=True,
                local_files_only=True,
            )
            self.device = "cuda"
        else:
            # CPU 场景使用 fp32 或量化加载（如果安装 bitsandbytes）
            try:
                self.model = transformers.AutoModelForCausalLM.from_pretrained(
                    self.model_path,
                    device_map="cpu",
                    trust_remote_code=True,
                    local_files_only=True,
                    load_in_8bit=True,
                )
                self.device = "cpu(8bit)"
            except Exception:
                self.model = transformers.AutoModelForCausalLM.from_pretrained(
                    self.model_path,
                    device_map="cpu",
                    trust_remote_code=True,
                    local_files_only=True,
                )
                self.device = "cpu"

        elapsed = time.time() - start
        if self.device and self.device.startswith("cuda"):
            mem = torch.cuda.memory_allocated() / 1024 ** 3
            print(f"[本地模型] 加载完成，耗时 {elapsed:.1f} 秒，设备: {self.device}，显存占用: {mem:.2f} GB")
        else:
            print(f"[本地模型] 加载完成，耗时 {elapsed:.1f} 秒，设备: {self.device}")

    def generate(
        self,
        prompt: str,
        system_prompt: str = "You are a helpful assistant.",
        max_new_tokens: int = 4096,
        temperature: float = 0.7,
        top_p: float = 0.9,
    ) -> dict:
        """生成文本，返回包含 text / usage 的字典。

        返回格式尽量与 DeepSeek API 一致，方便上层统一处理：
        {
            "text": "生成的文本",
            "usage": {
                "prompt_tokens": 123,
                "completion_tokens": 456,
                "total_tokens": 579,
            },
        }
        """
        self._load()

        # Qwen3 默认会进入 thinking 模式，追加 /no_think 关闭推理过程以获得直接回答
        if "/no_think" not in prompt and "/think" not in prompt:
            prompt = prompt.strip() + "\n/no_think"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        inputs = self.tokenizer(text, return_tensors="pt")
        input_ids = inputs.input_ids
        attention_mask = inputs.attention_mask

        if self.device and self.device.startswith("cuda"):
            input_ids = input_ids.to(self.model.device)
            attention_mask = attention_mask.to(self.model.device)

        prompt_tokens = input_ids.shape[1]

        start = time.time()
        with torch.no_grad():
            output = self.model.generate(
                input_ids,
                attention_mask=attention_mask,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p,
                do_sample=True,
                eos_token_id=self.tokenizer.eos_token_id,
                pad_token_id=self.tokenizer.pad_token_id or self.tokenizer.eos_token_id,
            )
        elapsed = time.time() - start

        generated_tokens = output[0][prompt_tokens:]
        completion_tokens = len(generated_tokens)
        response_text = self.tokenizer.decode(
            generated_tokens, skip_special_tokens=True
        ).strip()

        # 清理 Qwen3 可能残留的停止词后缀
        response_text = re.sub(r"<\|im_end\|>.*", "", response_text, flags=re.DOTALL).strip()

        # 移除 Qwen3 的 <think>...</think> 推理过程，只保留最终答案
        # 模型可能在 token 不足时未输出 </think>，因此遇到未闭合的 <think> 也截断到末尾
        response_text = re.sub(r"<think>.*?</think>", "", response_text, flags=re.DOTALL).strip()
        response_text = re.sub(r"<think>.*", "", response_text, flags=re.DOTALL).strip()

        return {
            "text": response_text,
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
            "elapsed": elapsed,
        }


def get_client(model_path: str) -> LocalLLMClient:
    """获取本地模型客户端实例。"""
    return LocalLLMClient(model_path)


def reset_client():
    """释放已加载的本地模型（用于内存紧张时手动释放）。"""
    inst = LocalLLMClient._instance
    if inst is not None:
        inst.model = None
        inst.tokenizer = None
        inst._initialized = False
        LocalLLMClient._instance = None
        import gc
        gc.collect()
        try:
            import torch as _torch
            _torch.cuda.empty_cache()
        except Exception:
            pass
        print("[本地模型] 已释放")
