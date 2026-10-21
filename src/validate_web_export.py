"""Validate every browser history and compare selected histories to Python/DuckDB."""

import json
from pathlib import Path
import subprocess
import tempfile

try:
    from product_data import ProductDataStore
except ModuleNotFoundError:
    from src.product_data import ProductDataStore

ROOT=Path(__file__).resolve().parents[1]


def main():
    destination=ROOT/'outputs/web_export_validation.json'
    destination.write_text(json.dumps({'passed':False,'status':'running'})+'\n')
    store=ProductDataStore()
    products=store.products()
    ids=list(dict.fromkeys([products.iloc[0].article_id,products.iloc[len(products)//2].article_id,
                            products.iloc[-1].article_id,'0372860002','0743234003']))
    reference=[]
    for article_id in ids:
        frame=store.history(article_id)
        frame['date']=frame.date.dt.strftime('%Y-%m-%d')
        reference.append({'profile':{'article_id':article_id},'rows':json.loads(frame.to_json(orient='records',double_precision=15))})
    with tempfile.TemporaryDirectory() as temporary:
        path=Path(temporary)/'reference.json'
        path.write_text(json.dumps(reference))
        result=subprocess.run(['node',str(ROOT/'web/scripts/check-data.mjs'),str(ROOT/'web/public/data'),str(path)],cwd=ROOT,text=True,capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    report=json.loads(result.stdout)
    destination.write_text(json.dumps(report,indent=2)+'\n')
    print(result.stdout.strip())


if __name__=='__main__':
    main()
