# OpenAPI

`openapi.json` نسخة مثبتة من عقد الـ API، مصدَّرة من FastAPI.

لإعادة توليدها بعد تغيير المسارات، مع تشغيل الخلفية:

```bash
curl http://localhost:8000/openapi.json -o openapi/openapi.json
```

أو من داخل بايثون:

```bash
python -c "import urllib.request,json; open('openapi/openapi.json','w',encoding='utf-8').write(json.dumps(json.load(urllib.request.urlopen('http://localhost:8000/openapi.json')),ensure_ascii=False,indent=2))"
```

هذا العقد هو مصدر توليد أنواع العميل (types) وعميل API المشترك بين الموقع
وتطبيق الهاتف لاحقًا (انظر `docs/WEB_MOBILE_ROADMAP_AR.md`). يجب فحص كسر
التوافق (oasdiff) في CI قبل دمج أي تغيير غير متوافق.

المصدر الحي أثناء التطوير: <http://localhost:8000/openapi.json> و
واجهة Swagger: <http://localhost:8000/docs>
