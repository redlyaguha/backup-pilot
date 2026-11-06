import tempfile
import unittest
from pathlib import Path

from backup_pilot.cli import main

class SmokeTest(unittest.TestCase):
    def test_e2e_backup_with_exclusions(self):
        """Автоматизированный профиль -> backup -> проверка файла и исключения в изолированном временном каталоге."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "source"
            dest = root / "destination"
            profiles = root / "profiles"
            
            src.mkdir()
            dest.mkdir()
            profiles.mkdir()

            # Создаем тестовые файлы: один обычный, один исключаемый
            (src / "keep.txt").write_text("keep me", encoding="utf-8")
            (src / "skip.tmp").write_text("exclude me", encoding="utf-8")

            # Создаем TOML-профиль
            profile_content = f"""
name = "demo"
source = "{src.as_posix()}"
destination = "{dest.as_posix()}"
exclude = ["*.tmp"]
keep_last = 1
schedule = "daily"
"""
            (profiles / "demo.toml").write_text(profile_content.strip(), encoding="utf-8")

            # Запускаем CLI (команду run demo)
            exit_code = main(["--profiles-dir", str(profiles), "run", "demo"])
            
            # Проверяем, что команда завершилась успешно (exit 0)
            self.assertEqual(exit_code, 0, "CLI вернул ошибку")

            # Проверяем, что снапшот создался
            snapshots = list((dest / "demo").iterdir())
            self.assertEqual(len(snapshots), 1, "Снапшот не создан")
            
            # Проверяем содержимое снапшота
            snapshot_data = snapshots[0] / "data"
            self.assertTrue((snapshot_data / "keep.txt").exists(), "Обычный файл не скопирован")
            self.assertFalse((snapshot_data / "skip.tmp").exists(), "Исключенный файл попал в бэкап")

    def test_missing_source_fails_red(self):
        """Unit-тест: отказ отсутствующего источника (падение основной функции делает тест красным)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profiles = root / "profiles"
            profiles.mkdir()

            # Профиль указывает на несуществующий source
            profile_content = f"""
name = "demo"
source = "{(root / 'absent').as_posix()}"
destination = "{(root / 'dest').as_posix()}"
exclude = []
keep_last = 1
schedule = "daily"
"""
            (profiles / "demo.toml").write_text(profile_content.strip(), encoding="utf-8")

            # Ожидаем, что CLI вернет код 2 (ошибка конфигурации)
            exit_code = main(["--profiles-dir", str(profiles), "profiles", "validate", "--config", str(profiles / "demo.toml")])
            self.assertEqual(exit_code, 2, "Ожидался код ошибки конфигурации 2")

if __name__ == '__main__':
    unittest.main()