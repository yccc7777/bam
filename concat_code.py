import os

target_folders = ['.', 'data', 'models', 'strategies', 'backtest', 'config']
output_file = 'ProjectChronos_CompleteCode.py'

# 排除輔助腳本及測試腳本
exclude_files = ['convert_to_word.py', 'generate_architecture_image.py', 'concat_code.py', 'ProjectChronos_CompleteCode.py', 'predict_custom.py', 'test_pipeline.py']

with open(output_file, 'w', encoding='utf-8') as out:
    for folder in target_folders:
        if not os.path.isdir(folder): continue
        for file in sorted(os.listdir(folder)):
            if file.endswith('.py') and file not in exclude_files:
                path = os.path.join(folder, file)
                out.write(f"\n\n{'='*80}\n")
                out.write(f"# 🗂️ 檔案位置 / FILE: {path}\n")
                out.write(f"{'='*80}\n\n")
                
                with open(path, 'r', encoding='utf-8') as f:
                    out.write(f.read())
                
                out.write("\n")
