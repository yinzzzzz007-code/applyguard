"""Validate the configured SAG cache without model calls or personal documents."""
import argparse,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
sys.stdout.reconfigure(encoding='utf-8')
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--directory',type=Path)
args=parser.parse_args()
from backend.app import _load_dotenv
from backend.services.sag_storage import check_index_directory
directory=(args.directory or Path(os.getenv('APPLYGUARD_GROUNDING_DIR',ROOT/'data/local/grounding'))).resolve()
try:
    check_index_directory(str(directory));print('SAG_STORAGE_OK '+str(directory))
except Exception as error:
    print('SAG_STORAGE_UNAVAILABLE '+str(directory));print(str(error));raise SystemExit(1)
