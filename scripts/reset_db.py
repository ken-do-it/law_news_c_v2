"""SQLite 데이터베이스 초기화 (파일 삭제)"""
import sys, os, io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def main():
    db_path = Path(__file__).resolve().parent.parent / 'backend' / 'db.sqlite3'

    if db_path.exists():
        os.remove(db_path)
        print(f'\n🗑️  DB 삭제됨: {db_path}')
    else:
        print(f'\n📂 DB 파일이 없습니다: {db_path}')


if __name__ == '__main__':
    main()
