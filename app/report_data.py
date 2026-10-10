"""Validation and matching of aggregated household and supplied Maps data."""
import re, unicodedata
from urllib.parse import urlparse, parse_qs, unquote
from fastapi import HTTPException

AGE_GROUPS={'age_0_5':'0 a 5 años','age_6_17':'6 a 17 años','age_18_59':'18 a 59 años','age_60_plus':'60 años o más'}
COUNT_FIELDS={**AGE_GROUPS,'people_disability':'Personas con discapacidad'}

def household(raw):
    family=str(raw.get('family_name') or '').strip()
    if not family or len(family)>300: raise HTTPException(422,'Indique el nombre de la familia (máximo 300 caracteres)')
    values={'family_name':family}
    for field in ('total_people',*COUNT_FIELDS):
        value=raw.get(field)
        if field!='total_people' and (value is None or value==''):
            values[field]=None;continue
        if isinstance(value,bool) or not re.fullmatch(r'\d{1,4}',str(value if value is not None else '')): raise HTTPException(422,'Las cantidades deben ser números enteros')
        n=int(value)
        if n< (1 if field=='total_people' else 0) or n>1000: raise HTTPException(422,'Cantidad inválida (máximo 1000 personas)')
        values[field]=n
    total=values['total_people'];ages=[values[k] for k in AGE_GROUPS]
    if sum(n or 0 for n in ages)>total or (all(n is not None for n in ages) and sum(ages)!=total):
        raise HTTPException(422,'La composición por edades debe coincidir con el total; los grupos omitidos quedan sin informar')
    if values['people_disability'] is not None and values['people_disability']>total:
        raise HTTPException(422,'Las personas con discapacidad no pueden superar el total; ya están incluidas en los grupos de edad')
    return values

def coordinates(link):
    u=urlparse(link);p=unquote(u.path);q=parse_qs(u.query)
    if '/dir/' in p or p.endswith('/dir'): return None
    candidates=q.get('q',[])+q.get('query',[])
    # Selected-place coordinates can occur in the path or in a data query.
    for lat,lon in re.findall(r'!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)',p+'?'+unquote(u.query)):
        candidates.append(lat+','+lon)
    points=set()
    for value in candidates:
        m=re.fullmatch(r'\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*',value)
        if m:
            lat,lon=map(float,m.groups())
            if -90<=lat<=90 and -180<=lon<=180: points.add((lat,lon))
    if len(points)==1:
        lat,lon=points.pop();return {'latitude':lat,'longitude':lon}
    return None

def normal(value):
    return ' '.join(unicodedata.normalize('NFKC',str(value if value is not None else '')).casefold().split())

def matching_keys(data,sign):
    phone=data['phone'];location='|'.join(normal(data[k]) for k in ('province','district','township','community'))
    place=data.get('coordinates');identity=normal(data.get('family_name') or data.get('name'))
    keys=[sign('phone-map|'+phone+'|'+data['maps'].rstrip('/')),sign('phone-sector|'+phone+'|'+location),sign('family-sector|'+identity+'|'+location)]
    if place:
        point=f"{place['latitude']:.5f},{place['longitude']:.5f}"
        keys.extend([sign('phone-point|'+phone+'|'+point),sign('family-point|'+identity+'|'+point)])
    return sorted(set(keys))
