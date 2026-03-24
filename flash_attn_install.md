# FlashAttention2 설치 가이드 (`RomanceArena`)

이 문서는 `/home/hosung/pytorch-demo/RomanceArena` 프로젝트에서  
`date_saya_backend`가 사용하는 Kanana VLM 계열 모델을 실행하기 위해 `flash-attn`을 설치하는 절차를 정리한다.

핵심 전제:

- 현재 `date_saya_backend/model_assets/saya_vlm_3b`의 remote `modeling.py`는 vision encoder 초기화 시 `flash_attention_2` 경로를 사실상 요구한다.
- 따라서 이 프로젝트에서는 `flash-attn`이 선택 사항이 아니라 **실행 필수 의존성**이다.
- 모델 파일 자체는 수정하지 않고, `RomanceArena`의 `uv` 환경에 의존성을 설치하는 기준으로 설명한다.

## 1. 적용 대상

다음 실행 경로가 이 문서의 대상이다.

```bash
cd /home/hosung/pytorch-demo/RomanceArena
uv run uvicorn date_saya_backend.api:app --host 0.0.0.0 --port 8010
```

위 명령에서 아래 오류가 나면 이 문서를 따르면 된다.

```text
ImportError: FlashAttention2 has been toggled on, but it cannot be used ...
the package flash_attn seems to be not installed
```

## 2. 전제 조건

- WSL2 또는 Linux 환경
- NVIDIA 드라이버 정상 동작
- CUDA 대응 PyTorch가 이미 설치된 `RomanceArena`의 `uv` 환경
- `ninja-build`, `build-essential` 같은 기본 빌드 도구 설치 가능 상태

먼저 프로젝트 루트에서 GPU/PyTorch 상태를 확인한다.

```bash
cd /home/hosung/pytorch-demo/RomanceArena
uv run python -c "import torch; print(torch.__version__, torch.version.cuda); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'no_gpu')"
```

## 3. 현재 프로젝트 환경 확인

`RomanceArena`는 `uv` 기반 프로젝트다. 설치는 반드시 이 프로젝트 루트에서 진행한다.

```bash
cd /home/hosung/pytorch-demo/RomanceArena
uv sync
```

현재 `date_saya_backend`는 다음 의존성을 이미 사용한다.

- `transformers`
- `bitsandbytes`
- `accelerate`
- `timm`

여기에 `flash-attn`만 추가로 맞추면 된다.

## 4. CUDA Toolkit 확인

`flash-attn`은 로컬 빌드가 필요한 경우가 많다. `nvcc`가 잡히는지 먼저 확인한다.

```bash
nvcc --version
```

없다면 Ubuntu/WSL에서 CUDA toolkit을 설치한다. 예시는 CUDA 12.8 기준이다.

```bash
cd /tmp
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb
sudo apt-get update
sudo apt-get install -y build-essential ninja-build cuda-toolkit-12-8
```

환경 변수:

```bash
echo 'export CUDA_HOME=/usr/local/cuda-12.8' >> ~/.bashrc
echo 'export PATH=$CUDA_HOME/bin:$PATH' >> ~/.bashrc
echo 'export LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH' >> ~/.bashrc
source ~/.bashrc
```

## 5. `RomanceArena` 환경에 FlashAttention2 설치

프로젝트 루트에서 실행한다.

```bash
cd /home/hosung/pytorch-demo/RomanceArena
```

기존 설치 흔적이 있으면 먼저 지운다.

```bash
uv pip uninstall -y flash-attn
rm -rf ~/.cache/uv/sdists-v9/pypi/flash-attn
rm -rf ~/.cache/pip
```

설치 전 권장 환경 변수:

```bash
export CUDA_HOME=/usr/local/cuda-12.8
export PATH=$CUDA_HOME/bin:$PATH
export MAX_JOBS=1
export NVCC_THREADS=1
```

RTX 50xx 계열처럼 최신 아키텍처면, 아키텍처를 고정해서 빌드 시간을 줄인다.

```bash
export FLASH_ATTN_CUDA_ARCHS="120"
```

설치:

```bash
uv pip install --no-build-isolation --no-cache-dir flash-attn
```

## 6. 설치 확인

```bash
cd /home/hosung/pytorch-demo/RomanceArena
uv run python -c "import flash_attn; print(flash_attn.__version__)"
```

추가 확인:

```bash
uv run python -c "import torch; import flash_attn; print('torch', torch.__version__); print('cuda', torch.version.cuda)"
```

## 7. 설치 중 멈춘 것 같을 때

진행 확인:

```bash
ps -ef | rg -i "uv pip install flash-attn|ninja|nvcc|cicc" | rg -v rg
```

CPU 점유율 확인:

```bash
top -H -p $(pgrep -d',' -f "ninja|nvcc|cicc|uv pip install flash-attn")
```

아래 상태면 사실상 멈춘 경우가 많다.

- `ninja`만 남고 `nvcc/cicc`가 사라짐
- CPU 사용률이 계속 0%

정리 후 재시도:

```bash
pkill -f "flash-attn|ninja|nvcc|cicc"
rm -rf /tmp/.tmp*/sdists-v9/pypi/flash-attn
rm -rf ~/.cache/uv/sdists-v9/pypi/flash-attn
```

그 다음 5단계부터 다시 진행한다.

## 8. 자주 나는 오류와 의미

### `No module named 'flash_attn'`

- 설치가 실패했거나 완료되지 않았다.

### `FlashAttention2 has been toggled on ... package flash_attn seems to be not installed`

- 현재 `date_saya_backend`가 로드하는 Kanana VLM 구현은 FlashAttention2 경로를 탄다.
- 이 프로젝트 기준으로는 `flash-attn` 설치가 필요하다.

### `CUDA error: no kernel image is available for execution on the device`

- 현재 GPU 아키텍처에 맞지 않게 빌드되었다.
- RTX 50xx 계열이면 `FLASH_ATTN_CUDA_ARCHS="120"`으로 다시 빌드한다.

### `subprocess-exited-with-error` 또는 wheel build 실패

- CUDA toolkit / `nvcc` / `ninja` / PyTorch-CUDA 조합 문제일 가능성이 크다.
- `torch.__version__`, `torch.version.cuda`, `nvcc --version`을 같이 확인한다.

## 9. 백엔드 실행 확인

설치 후 다시 백엔드를 띄운다.

```bash
cd /home/hosung/pytorch-demo/RomanceArena
uv run uvicorn date_saya_backend.api:app --host 0.0.0.0 --port 8010
```

정상 기동 후 health 체크:

```bash
curl http://127.0.0.1:8010/health
```

## 10. 배포 시 원칙

이 프로젝트는 나중에 배포할 때도 수동 설치를 반복하면 안 된다.  
따라서 배포 환경은 아래 원칙으로 맞춘다.

- `flash-attn`이 포함된 **검증된 Docker 이미지**를 사용한다.
- 런타임 컨테이너 안에 다음을 고정한다.
  - CUDA 버전
  - PyTorch 버전
  - `flash-attn`
  - `transformers`
  - `bitsandbytes`
  - `timm`
- 배포 시에는 `uvicorn date_saya_backend.api:app ...`만 실행되도록 한다.

즉, 개발 환경에서는 이 문서대로 설치하고, 운영 환경에서는 설치가 끝난 이미지를 배포하는 게 맞다.
