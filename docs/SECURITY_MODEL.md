# Cannab'IA — Modelo de Ameaça e Plano de Segurança

## 1) Superfícies de ataque

1. **Webhook público (`/webhook`)**
   - Riscos: spoofing, replay, flood, payload malicioso, parsing inseguro.

2. **Painéis web (`/dashboard`, `/historico`, `/scheduling`, `/realtime`)**
   - Riscos: acesso indevido, vazamento de dados clínicos, CSRF, brute force de login.

3. **Canal Socket.IO**
   - Riscos: assinante não autenticado recebendo eventos sensíveis em tempo real.

4. **Integrações externas (WhatsApp/SMTP)**
   - Riscos: vazamento de tokens/credenciais, abuso de APIs, exfiltração por logs.

5. **Banco de dados MySQL**
   - Riscos: permissões excessivas, backups sem criptografia, exposição de PHI.

6. **Módulos de IA (LLM/LangChain, quando usados em produção)**
   - Riscos: prompt leakage, retenção indevida de PHI em logs/traces.

---

## 2) Controles já implementados (P0 atual)

- **Autenticação e RBAC** por perfil (`Admin`, `Medico`, `Atendente`).
- **Proteção de rotas críticas** por autorização explícita.
- **CSRF** em login, logout e agendamento.
- **Sessão endurecida** (`Secure`, `HttpOnly`, `SameSite`).
- **Rate limiting** para login e webhook (por IP, memória local).
- **Webhook com tamanho máximo e validação básica de payload**.
- **Socket.IO autenticado** (bloqueia conexão sem sessão válida).
- **Redaction** de dados sensíveis em logs/eventos.
- **Headers de segurança** (CSP, HSTS, X-Frame-Options, etc.).
- **`.env.example` sem segredos** para setup seguro.

---

## 3) Gaps críticos (P1)

1. **Autenticação de produção**
   - Usuários ainda em variável JSON (POC).
   - Falta senha hash (bcrypt/argon2), política de senha e MFA.

2. **Webhook anti-spoofing/replay completo**
   - Falta assinatura criptográfica do provedor.
   - Falta idempotência persistida (`event_id/message_id`).

3. **Rate limit distribuído**
   - Implementação atual é em memória local por processo.

4. **Proteção de PHI em repouso**
   - Falta criptografia de campos clínicos com chaves fora do banco.

5. **Auditoria e conformidade LGPD**
   - Falta trilha detalhada de acesso (quem viu qual dado e quando).

---

## 4) Políticas internas recomendadas (obrigatórias)

- Não enviar anamnese completa por WhatsApp sem consentimento explícito.
- Não enviar relatório clínico completo por e-mail sem mecanismo seguro adequado.
- Não registrar prompts/respostas LLM com PHI em logs.
- Nunca logar payload completo de webhook em produção.

---

## 5) Checklist objetivo (próxima sprint)

### P0 imediato
- [ ] Migrar usuários para DB + senha hash.
- [ ] Implementar assinatura de webhook.
- [ ] Implementar idempotência persistida.
- [ ] Mover rate limit para Redis.

### P1
- [ ] Criptografia de campos PHI.
- [ ] Auditoria por paciente/usuário.
- [ ] Métricas e alertas de segurança.

### P2
- [ ] Revisão formal de ameaça com periodicidade.
- [ ] Testes de segurança automatizados (SAST/DAST e cenários de abuso).
