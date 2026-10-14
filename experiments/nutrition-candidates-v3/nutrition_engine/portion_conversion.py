"""Convert AUSNUT measures by their own food key, with explicit ambiguity checks."""
import sqlite3
import math
from contextlib import closing

def convert_measure(db_path, public_food_key, descriptor, quantity, measure_id=None):
    if isinstance(quantity,bool) or not isinstance(quantity,(int,float)) or not math.isfinite(quantity) or quantity<0:raise ValueError('Invalid quantity')
    with closing(sqlite3.connect(db_path)) as c:
        c.row_factory=sqlite3.Row
        if measure_id:
            rows=c.execute('SELECT * FROM measures WHERE measure_id=? AND public_food_key=?',(measure_id,public_food_key)).fetchall()
        else:
            rows=c.execute('SELECT * FROM measures WHERE public_food_key=? AND lower(descriptor)=lower(?)',(public_food_key,descriptor)).fetchall()
    if len(rows)!=1:raise ValueError('REVIEW_REQUIRED: measure is missing or ambiguous; supply an exact measure_id')
    r=rows[0]
    if not r['quantity'] or r['grams'] is None:raise ValueError('REVIEW_REQUIRED: no valid gram conversion')
    return {'grams':quantity/r['quantity']*r['grams'],'measure_id':r['measure_id'],
            'source_id':r['source_id'],'public_food_key':r['public_food_key'],'source_row':r['source_row']}
