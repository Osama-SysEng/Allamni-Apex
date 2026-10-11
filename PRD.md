# PRD — Allamni-Apex (AI Adaptive Education OS)

## 1. نظرة عامة
نظام تشغيل تعليمي تكيّفي: ملف تعلم رقمي، تقييم، توليد خطط، شات تعليمي، إدارة مؤسسات، تكامل Odoo. بوابة `api_gateway` تُوَكّل لخمس خدمات (auth :8001، learning :8002، ai :8003، integration :8004، institution :8005).

## 2. المستخدمون
- طالب (ملف ذكي، تقييم، خطة، شات)
- معلم (مساعد، تحليلات)
- مؤسسة/مدير (أكواد، اشتراكات، فواتير، تقارير)

## 3. الميزات الأساسية (قابلة للاختبار)
1. تسجيل/دخول بأنواع (مؤسسة، كود طالب/معلم، ذاتي) + تجديد/خروج (`POST /register*|/login|/refresh|/logout`)
2. تحليلات الطالب: ذكاء، إجراء تالٍ، مخطط درس، ذاكرة (`GET /students/me|/intelligence|/next-best-action|/lesson-blueprint|/memory`)
3. تقديم تقييم وخطة محتوى (`POST /students/me/assessments/submit`, `POST /students/me/content/plan`)
4. شات تعليمي وشرح وتحليل صورة/صوت (`POST /students/chat|/explain|/arabic-nlp|/image-analysis|/voice-transcribe`, `POST /chatbot/start|/message`)
5. مساعد معلم ورؤى مؤسسة (`POST /teachers/assistant`, `POST /institutions/insights`, `GET /institution/intelligence`)
6. إشعارات كاملة (`POST /notifications`, `GET /notifications/{user_id}[|/unread-count|/preferences]`, `PUT .../read|.../preferences`)
7. إدارة مؤسسات: أكواد، لوحة، طلاب/معلمون، اشتراك، فواتير (`/codes/*`, `/institutions/{id}/*`, `/invoices/*`)
8. تكامل Odoo: طابور/مزامنة/حالة (`POST /odoo/queue|/sync[/entity|/bulk|/trigger]`, `GET /odoo/status|/config|/sync/history`)
9. أمان: 2FA، بيومتري، جلسات، تشفير (`POST /auth/2fa/*|/auth/biometric/*`, `GET /auth/sessions|/security/*`)

## 4. API endpoints الحقيقية (من الكود فقط)
- Gateway: `GET /health` + توكيل حسب البادئة لعناوين `AUTH|LEARNING|AI|INTEGRATION|INSTITUTION_URL`
- Auth-Service: `POST /register|/login|/refresh|/logout|/me/consent|/register/institution|/register/student-code|/register/teacher-code|/register/self|/auth/2fa/setup|/auth/2fa/verify|/auth/biometric/register|/auth/biometric/verify|/auth/sessions/{id}/revoke|/security/encrypt|/security/decrypt`, `GET /auth/sessions|/auth/security-events|/security/metrics|/security/scan`
- Learning-Service: `GET /students/me|/intelligence|/next-best-action|/lesson-blueprint|/memory|/institution/intelligence|/admin/analytics/overview`, `POST /students/me/assessments/submit|/content/plan|/consent|/admin/resources`
- AI-Service: `POST /students/analyze|/generate-plan|/generate|/chat|/explain|/voice-transcribe|/arabic-nlp|/image-analysis|/teachers/assistant|/institutions/insights|/learning/record-signal|/chatbot/start|/message|/notifications`, `GET /learning/metrics|/patterns|/chatbot/conversation/{id}|/chatbot/analytics/{user_id}|/notifications/{user_id}*`
- Institution-Service: `POST /codes/student/generate|/codes/teacher/generate`, `GET|DELETE /codes/*`, `GET|PUT|DELETE /institutions/{id}*` (dashboard/students/teachers/subscription/analytics/reports/billing/invoices)، `GET /invoices/{id}`, `POST /invoices/{id}/payments`, `PUT /invoices/{id}/status`
- Integration-Service: `POST /odoo/queue|/sync/entity|/bulk|/trigger|/sync`, `GET /odoo/config|/sync/history|/status`, `PUT /odoo/config`

## 5. بيانات الدخول/الإعداد للاختبار
- `cp .env.example .env` ثم `docker compose up --build`؛ API: `http://localhost:8000`، Swagger: `/docs`
- الاختبارات: `cd backend && python -m pytest -q`؛ لا مستخدمين افتراضيين في الكود — التسجيل عبر `/register*`

## 6. خارج النطاق (mocked/simulated)
- LLM الحقيقي وOdoo الحي والتخزين السحابي وبيانات الإنتاج: حسب README نفسه «environment-specific» والوضع التطويري بديل حتمي مُعلَّم صراحة — لا يُختبر أي تكامل خارجي كأنه حي.
