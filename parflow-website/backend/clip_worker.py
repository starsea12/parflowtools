import subprocess
import sys
import zipfile
from pathlib import Path

def run_clip(watershed_ids, output_dir):
    """
    调用 run_two.py 裁剪程序，并打包结果
    """
    if not watershed_ids:
        raise ValueError("流域编号列表为空")

    # 取第一个编码（run_two.py 一次只处理一个）
    basin_code = str(watershed_ids[0]).strip()
    print(f"[DEBUG] 传入的流域编码: '{basin_code}', 长度: {len(basin_code)}")

    if len(basin_code) != 14:
        raise ValueError(f"流域编码长度应为14位，实际为: {len(basin_code)} (内容: '{basin_code}')")
    if not basin_code.isdigit():
        raise ValueError(f"流域编码必须为纯数字，实际为: '{basin_code}'")

    backend_dir = Path(__file__).resolve().parent
    run_script = backend_dir / 'run_two.py'   # 请确认文件名

    if not run_script.exists():
        raise FileNotFoundError(f"裁剪主程序未找到: {run_script}")

    input_data = f"{basin_code}\n"

    # ★★★ 关键：使用当前环境的 Python（确保与 Flask 环境一致） ★★★
    # 如果 run_two.py 依赖特殊环境，建议在启动 Flask 前激活对应的 conda 环境
    result = subprocess.run(
        [sys.executable, str(run_script)],
        input=input_data,
        capture_output=True,
        text=True,
        cwd=str(backend_dir)
    )

    print("=== run_two.py STDOUT ===")
    print(result.stdout)
    print("=== run_two.py STDERR ===")
    print(result.stderr)

    if result.returncode != 0:
        error_msg = (
            f"裁剪程序执行失败 (返回码 {result.returncode}):\n"
            f"STDOUT: {result.stdout}\n"
            f"STDERR: {result.stderr}"
        )
        raise RuntimeError(error_msg)

    result_dir = backend_dir / 'outputs' / basin_code
    if not result_dir.exists():
        raise RuntimeError(f"裁剪程序未生成预期目录: {result_dir}")

    zip_filename = f"clip_result_{basin_code}.zip"
    zip_path = Path(output_dir) / zip_filename

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file_path in result_dir.rglob('*'):
            if file_path.is_file():
                arcname = file_path.relative_to(result_dir.parent)
                zf.write(file_path, arcname)

    print(f"[DEBUG] 打包完成: {zip_path} (大小: {zip_path.stat().st_size / 1024:.2f} KB)")
    return str(zip_path)