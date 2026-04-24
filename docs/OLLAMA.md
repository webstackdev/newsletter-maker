## Ollama and LLM Models

Ollama is an open-source tool designed to run Large Language Models (LLMs) like Llama 3, Mistral, and Gemma directly on your local machine (Windows, macOS, Linux). It simplifies the process of setting up and running AI models, providing a user-friendly CLI to download and manage them without needing complex configurations or cloud subscriptions.

- Running AI coding assistants.
- Building local RAG (Retrieval-Augmented Generation) applications.
- Chatting with local models for privacy-sensitive work.

## Model Vendors

- **Llama (3, 3.1, 4):** Developed by Meta (Facebook). It is a highly influential open-weight model family, known for its general reasoning and ecosystem support.
- **Gemma (2, 3, 4):** Built by Google DeepMind. These models use the same research and technology as Google's Gemini models but are optimized for local performance.
- **Mistral / Mixtral:** Created by Mistral AI, a French company. They use the "Mixture of Experts" (MoE) architecture. This allows the models to be intelligent and efficient enough to run on consumer hardware.
- **DeepSeek-R1 (by DeepSeek-AI):** This model is designed for reasoning. It is considered one of the highest-rated open models for math, logic, and reasoning.
- **Qwen (3, 3.5) (by Alibaba Cloud):** It is considered one of the best models for coding and technical tasks. It often outperforms other open models in programming benchmarks.
- **Command R / R+ (by Cohere):** This model is designed for RAG (Retrieval-Augmented Generation). It is optimized for using long documents as context and is useful for tasks like summarization and professional writing.

## Speed

| Model Size                      | Where it runs  | Estimated Speed (Tokens/Sec) | User Experience                            |
| :------------------------------ | :------------- | :--------------------------- | :----------------------------------------- |
| **8B (Llama 3, Qwen)**          | Mostly GPU     | **15–20+ t/s**               | Very fast; faster than a human can read.   |
| **14B–32B (Gemma, DeepSeek)**   | Split GPU/CPU  | **3–8 t/s**                  | Usable; like watching a fast typist.       |
| **70B+ (Llama 3.1, Command R)** | Mostly CPU/RAM | **1–2 t/s**                  | Very slow; best for long background tasks. |

## Quant

The "B" refers to number of parameters in billions. A larger model at low quantization usually beats a small model at high quantization. For example, a **Llama 70B** compressed to **4-bit (Q4)** will almost always be much smarter than a **Llama 8B** running at "perfect" **16-bit (FP16)**, even though they might take up similar amounts of RAM. The jump in "intelligence" from a high-quality 8-bit (Q8) version to the full 16-bit version is mathematically measurable but practically invisible to a human user. 

- **FP16 (16-bit):** The "original" high-quality version. It uses 2 bytes per number. A 7B model takes ~14GB of RAM.
- **Q8 (8-bit):** Uses 1 byte per number. This is almost indistinguishable from the original in quality but cuts the RAM requirement in half (~7GB for a 7B model).
- **Q4 (4-bit):** The "sweet spot." It uses only half a byte per number. A 7B model now only needs ~3.5GB to 4GB of RAM. You lose about 1–5% in accuracy, but the model becomes 3–4x faster.
- **Q2 (2-bit):** Extreme compression. The model becomes very small and fast, but it often starts to "hallucinate" or lose its ability to follow complex logic.

**Decoding the Suffixes (e.g., Q4_K_M)**

- **Q4:** The number of bits (4-bit).
- **_K:** "K-Quants," a modern method that uses higher precision for the most important parts of the model and lower precision for the less important ones.
- **_S, _M, _L:** Small, Medium, or Large versions of that bit-level. **_M (Medium)** is usually the recommended default as it balances size and smarts perfectly.

## Large Models

- **Llama 3.1 405B:** This is currently one of the largest open-weight models. At full FP16 precision, it requires over **800GB**, but using 4-bit (INT4) quantization, it fits into roughly **203GB to 256GB**. A 512GB workstation can run this comfortably while leaving room for a massive context window (KV cache).
- **DeepSeek-V3 (671B):** This "MoE" (Mixture of Experts) model is massive but efficient. At 4-bit quantization, it needs approximately **405GB**. Running this requires the exact 512GB RAM setup you described.
- **Qwen 3.5 397B:** Another massive MoE model that typically requires nearly **200GB to 400GB** depending on the quantization level used.

## Availability and Licensing

- **[Llama 3.1](https://ai.meta.com/blog/meta-llama-3-1/) (Meta):** Available for local download and use via [Ollama](https://ollama.com/library/llama3.1) and Hugging Face. It is released under the **Llama 3.1 Community License**, which allows for free commercial and research use for most users. However, companies with over **700 million** monthly active users must request a separate license, and it includes specific "Acceptable Use" restrictions.
- **[DeepSeek-V3](https://github.com/deepseek-ai/deepseek-v3) (DeepSeek-AI):** This model is widely considered "open-weight" and is free to run locally. While originally under a custom license, DeepSeek recently moved their flagship models to the **MIT License**, which is a standard, highly permissive open-source license allowing for unrestricted commercial use, modification, and distribution.
- **[Qwen 3.5](https://www.reddit.com/r/DeepSeek/comments/1s1nesc/qwen_35_vs_deepseekv3_which_opensource_model_is/) (Alibaba Cloud):** Like its predecessors, it is released under the **Apache 2.0 License**, another standard permissive open-source license used for commercial production.

## AMD GPU

ROCm allows using AMD GPUs with Llama. The 5000 series is not "officially" supported in the latest professional enterprise lists, it works reliably using a simple override command. After a standard Ollama installation, you just set an environment variable: HSA_OVERRIDE_GFX_VERSION=10.1.0. A 16GB card can hold a 14B model *plus* a large amount of "context" (the documents you are chatting with) entirely on the GPU.

**The "Sweet Spot" for Your 128GB Build**

Since you have 128GB, your "Full Quality" ceiling is actually the **70B/72B class** of models:

| Model                  | Recommended Quant  | Approx. Size | Logic for your Setup                                         |
| :--------------------- | :----------------- | :----------- | :----------------------------------------------------------- |
| **Llama 3.1 70B**      | **Q8_0 (8-bit)**   | ~75 GB       | **High Quality.** Since this is your "General Manager," you want the highest precision. It fits comfortably in 128GB with 50GB to spare. |
| **Qwen 2.5 72B**       | **Q6_K (6-bit)**   | ~58 GB       | **The "Smart" Compromise.** 6-bit is virtually indistinguishable from 8-bit but saves RAM for the messy HTML context you'll be feeding it. |
| **Command R+ (104B)**  | **Q4_K_M (4-bit)** | ~63 GB       | **Efficiency.** At 104B, 8-bit would consume 104GB+, leaving no room for your Vector DB data. 4-bit is the professional standard for this model. |
| **DeepSeek-V3 (671B)** | **IQ2_M (2-bit)**  | ~120 GB      | **Experimental.** This is a massive MoE model. At 2-bit, it will *barely* fit. It will be slow and may lose some nuance, but it's the only way to run it on 128GB. |
| **Gemma 2 27B (GPU)**  | Q4_K_M (4-bit)     | ~16 GB       | **Speed.** Fits on your **5800XT** for instant, high-speed drafting (20+ t/s). |
| **Gemma 2 27B (RAM)**  | Q8_0 (8-bit)       | ~29 GB       | **Quality.** Use this if you want the "perfect" version for drafting and don't mind CPU speeds. |

On your current setup, a **70B model at 8-bit** will be the "smartest" thing you can run comfortably with high reliability.

For Gemma:

- **On the GPU (16GB VRAM):** Use **4-bit**. This is the best way to get "ChatGPT-like" typing speeds for your final newsletter summaries.
- **In System RAM (128GB RAM):** Use **8-bit**. If you find the 4-bit version is losing too much "flair" in its writing, move it to your system RAM. It will be slower, but it will use its full 27B parameter "brain" at higher precision

## Model Choice

While **Llama 3.1 70B** is the "steady hand" for general logic, **DeepSeek-V3** and **Qwen 2.5/3.5** offer significant advantages for coding and structured data tasks. DeepSeek-V3 is currently the top-performing open-weight model for coding, often outperforming Llama 3.1 in complex Python and SQL tasks.

**Skill-by-Skill Recommendations**

| Skill                             | Best 70B Class Model  | Why?                                                         |
| :-------------------------------- | :-------------------- | :----------------------------------------------------------- |
| **1. Content Classification**     | **Llama 3.1 70B**     | Best-in-class instruction following. It handles "nuanced" categories (Opinion vs. Tutorial) with fewer hallucinations. |
| **2. Relevance Scoring**          | **Command R+ 104B**   | **The RAG Specialist.** It is specifically trained for "citation" and "grounding." It is better than almost any other model at explaining relevance based on a provided reference corpus. |
| **3. Deduplication / Clustering** | **Command R+ 104B**   | Its massive context window and "cross-referencing" training make it the best at comparing a new item against multiple existing records to pick a "winner." |
| **4. Summarization**              | **Gemma 2 27B**       | The "Punchy" Writer. Gemma 2 has a very modern, clean writing style that feels less "AI-generated" than Llama. At 27B, it’s fast enough to run entirely in your 16GB VRAM. Perfect for short tasks like 2–3 sentence newsletter summaries. |
| **5. Theme Detection**            | **DeepSeek-V3 (MoE)** | Excellent at "Global Reasoning." It can connect disparate dots across a large batch of ingested content to find emerging patterns. |
| **6. Email Data Extraction**      | **Qwen 2.5 72B**      | The "JSON King." Qwen is specifically optimized for structured data and HTML parsing; it is much less likely to break the JSON schema than Llama. |
| **7. Entity Extraction**          | **Qwen 2.5 72B**      | Extremely accurate at identifying obscure company names and matching them to existing profiles without making up new entities. |

Since you are automating a pipeline, you could have **Command R+** do the heavy analysis in the background (slowly), and then "hand off" the final notes to **Gemma 2** on the GPU to quickly write the user-facing text.

## Context Window RAM Size

### How to increase the context window

You can increase the context window from the model default in three ways:

1. **For a single session:**
   Inside the Ollama chat terminal (`ollama run llama3.1:70b...`), type:

   bash

   ```
   /set parameter num_ctx 32768
   ```

   *(Note: This resets when you exit the session)*.

2. **Permanently via a Modelfile:**
   Create a file named `Modelfile` and add these two lines:

   dockerfile

   ```
   FROM llama3.1:70b-instruct-q8_0
   PARAMETER num_ctx 32768
   ```

   Then, create your custom version:
   `ollama create llama3.1-70b-32k -f Modelfile`.

3. **Globally via Environment Variable:**
   Set `OLLAMA_NUM_CTX=32768` in your environment variables to apply it to all models by default.

### Model Memory Comparison Table

| Model                        | Install Command                                 | Max Context | Default Context | RAM at 2k / 8k / 32k | RAM at Max Context |
| :--------------------------- | :---------------------------------------------- | :---------- | :-------------- | :------------------- | :----------------- |
| **Llama 3.1 70B (Q8_0)**     | `ollama run llama3.1:70b-instruct-q8_0`         | 128k        | 2k–4k           | 76 / 78 / 86 GB      | ~132 GB (OOM)      |
| **Qwen 2.5 72B (Q4_K_M)**    | `ollama run qwen2.5:72b`                        | 128k        | 2k–4k           | 48 / 50 / 58 GB      | ~104 GB            |
| **Qwen3-Embedding:8b**       | `ollama pull qwen3-embedding:8b`                | 32k         | 32k             | 6 / 7 / 9 GB         | ~9 GB              |
| **Command R+ 104B (Q4_K_M)** | `ollama run command-r-plus:104b-08-2024-q4_K_M` | 128k        | 4k              | 64 / 67 / 79 GB      | ~144 GB (OOM)      |
| **Gemma 2 27B (Q4_K_M)**     | `ollama run gemma2:27b`                         | 8k          | 2k–8k           | 18 / 19 / N/A        | ~19 GB             |

Notice that **Qwen 2.5 72B** is much more efficient. Even though it is a similar size to Llama 70B, its "Max Context" RAM (~104 GB) fits on your machine because its KV Cache is architecturally smaller (it uses more efficient "Heads").

## Token Comparison

| Unit                                | Approx. Token Count                        |
| :---------------------------------- | :----------------------------------------- |
| **1 Word**                          | 1.3 Tokens                                 |
| **1 Standard Page (Single spaced)** | 500 – 700 Tokens                           |
| **1 MB of Plain Text**              | ~250,000 Tokens                            |
| **Ollama Default (2k-4k)**          | ~1,500 – 3,000 words (Small chapter)       |
| **Your "Safe" Max (32k)**           | ~24,000 words (Novelette/Technical Manual) |
