# PetGo — SPEC consolidada para Flask/MySQL/EC2

## Como usar

Copiar `.kiro/specs/petgo-mvp/` para o projeto e trabalhar na ordem `requirements.md` → `design.md` → `tasks.md`. A pasta `.kiro` pode ficar oculta no explorador de arquivos. São especificações prontas para orientar implementação; este pacote não contém aplicação executável nem cria recursos AWS.

## Documentos

- `requirements.md`: produto, critérios de aceitação e pontuação.
- `design.md`: arquitetura, dados, endpoints, transações e operação.
- `tasks.md`: plano de execução e matriz de aceite.
- `visual-reference.md`: referência visual preservada do design enviado, subordinada às regras novas.

## Resumo da pontuação proposta

| Situação | Quem publicou, incluindo +5 do cadastro | ONG participante elegível |
|---|---:|---:|
| Cadastro sem desfecho | 5 | 0 |
| Resgate ou adoção direta normal confirmado | 15 | 15, se houver ONG |
| Resgate ou adoção direta com risco aprovado | 25 | 40, se houver ONG |
| Adoção posterior a resgate já pontuado | Sem crédito adicional | Sem crédito adicional |

Interpretação adotada: bônus de risco substitui o normal, não se soma a ele. A pessoa que adota não recebe bônus próprio. Somente cadastro e primeiro desfecho confirmado geram pontos. São decisões explícitas de refinamento para revisar antes de codificar, não valores adicionais informados pelo solicitante.

## Conflitos corrigidos

| Origem | Conteúdo anterior | Decisão desta revisão |
|---|---|---|
| requirements(1).zip | CRUD pets Flask/MySQL; exclusão física e status livre | Incorporado ao ciclo validado, histórico e exclusão lógica |
| design(1).zip | API FastAPI/MySQL, SNS e alerta de pet localizado | Substituído por Flask e alertas de novo pet/adoção com outbox e e-mail direcionado |
| petgo-user-rescue-api-spec(1).zip | Plataforma NestJS/TypeScript/PostgreSQL/Prisma | Domínio de resgate/adoção preservado e adaptado a Flask/MySQL |
| Regras antigas | Só protetor verificado publica; aprovação já conclui adoção | Pessoa verificada pode publicar; adoção requer entrega/recebimento |
| Nova ideia | Gamificação e recompensas sem persistência definida | Carteiras, extrato, política única, estoque e voucher transacionais |

Não manter os documentos antigos ativos como fonte de verdade no Kiro: eles possuem tecnologias, nomes de estados e regras incompatíveis. Esta entrega consolidada é separada dos anexos para preservar os originais.

## Escopo comercial e operacional

MVP para hackathon, instância única, MySQL local na EC2. Sem orçamento, SLA de produção ou patrocínio contratado neste documento. Antes de produção: medir capacidade/custos, validar condições dos prêmios e ajustar operação conforme uso real.
