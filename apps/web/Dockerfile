# ============ البناء ============
FROM node:22-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# NEXT_PUBLIC_* تُدمج في حزمة المتصفح وقت البناء، لذا تمرر كـ build arg
ARG NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
# بصمة البناء: بها يُبطَل مخزن عامل الخدمة عند كل نشر. قيمة مختلفة لكل
# بناء (وسم الإصدار أو بصمة الالتزام)، وإلا بقي الزوار على نسخة قديمة.
ARG NEXT_PUBLIC_BUILD_ID=dev
ENV NEXT_PUBLIC_BUILD_ID=$NEXT_PUBLIC_BUILD_ID
ENV NEXT_TELEMETRY_DISABLED=1

RUN npm run build

# ============ التشغيل ============
FROM node:22-alpine

WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
# public/ لا تُدرج في standalone تلقائيًا؛ بدونها تسقط أيقونات التطبيق
# وعامل الخدمة (sw.js) فلا يعمل التثبيت على الهاتف ولا وضع بلا اتصال.
COPY --from=builder /app/public ./public

USER node

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:3000/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "server.js"]
