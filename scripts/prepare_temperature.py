"""Download and validate one NASA POWER/MERRA-2 monthly point series."""
from pathlib import Path
import sys
import argparse
import json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from saharawatch.temperature import fetch_temperature

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--latitude',type=float,required=True)
    parser.add_argument('--longitude',type=float,required=True)
    parser.add_argument('--start',type=int,default=1981)
    parser.add_argument('--end',type=int,default=2024)
    args=parser.parse_args()
    print('Loading real NASA POWER data (one point request if not cached).',flush=True)
    monthly,annual,provenance=fetch_temperature(args.latitude,args.longitude,args.start,args.end)
    print(json.dumps(provenance,indent=2))
    print(f'{monthly.size} monthly observations; {int(annual.count())} complete annual means in °C.')
