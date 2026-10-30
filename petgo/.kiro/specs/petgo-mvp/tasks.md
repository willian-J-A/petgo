# Implementation Plan — PetGo MVP

## Overview

Fonte de verdade: requirements.md e design.md desta pasta. Nenhuma tarefa foi implementada neste pacote. Todos os itens abaixo permanecem pendentes. Não reutilizar a stack ou as regras conflitantes dos pacotes anteriores.

## Tasks

- [x] 1. Criar base Flask e configuração
  - Application factory, Blueprints, SQLAlchemy/PyMySQL, Alembic, schemas, Flask-Login e CSRF.
  - Criar estrutura modular, lockfile validado, `.env.example`, configuração de desenvolvimento/testes e logs sanitizados.
  - Critério: app e healthcheck local funcionam, sem segredos no repositório. R10.

- [x] 2. Criar migrações MySQL
  - Implementar tabelas, FKs, constraints, colunas geradas e índices do design.
  - Implementar transações, locks, unicidade de idempotência, carteiras e lançamentos imutáveis.
  - Validar upgrade/restore em MySQL real, incluindo unicidade sob corrida. R03–R10.

- [x] 3. Implementar contas e sessão
  - Registro, verificação de e-mail, login/logout, recuperação, perfil, consentimento e preferências.
  - Hash seguro, autorização por recurso, CSRF e rate limiting.
  - Critério: conta não verificada não publica nem troca; senha/hash não sai na API. R01.

- [x] 4. Implementar ONG e parceiro
  - CNPJ, solicitação, decisão administrativa, membros e suspensão.
  - Parceiros com representantes e aprovação; carteiras institucionais isoladas.
  - Critério: representante removido perde acesso; ONG pendente não assume resgate. R02/R08.

- [x] 5. Implementar pets e mídia
  - Cadastro, campos opcionais desconhecidos, filtros, listas distintas, paginação e DTOs privados/públicos.
  - Upload validado, autorização de media_ids, exclusão lógica e limpeza de arquivos temporários.
  - Histórico e crédito +5 atômico, com idempotência.
  - Critério: rollback não cria pontos órfãos; usuário comum pode publicar. R03/R07/R10.

- [x] 6. Implementar risco e atendimento de resgate
  - Relato, validação administrativa, assunção exclusiva, comprovação, confirmação independente e cancelamento.
  - Critério: assumir não gera pontos; conclusão avança pet mesmo aguardando decisão de risco. R04/R06.

- [x] 7. Implementar adoção
  - Pedido normal/direto, revisão, reserva única, encerramento de concorrentes e cancelamento com estado de origem.
  - Confirmação de entrega e recebimento; concluir só após ambas; tratar sobreposição com administrador.
  - Critério: aprovação não equivale à entrega e não pontua. R05.

- [x] 8. Implementar política de pontos v1
  - Publicação +5; normal +10/+15; risco +20/+40; regra de ONG elegível.
  - Award único por fase, espera de risco, liquidação posterior, extrato e estorno compensatório.
  - Critério: resgate seguido de adoção pontua desfecho uma vez; saldo = soma do extrato. R06/R07.

- [x] 9. Implementar benefícios e vouchers
  - Catálogo, estoque, custo, validade, elegibilidade e termos versionados na troca.
  - Troca transacional, voucher seguro, uso único, cancelamento e expiração com devolução única.
  - Critério: corridas não causam estoque negativo, gasto duplo ou voucher usado e reembolsado. R08.

- [x] 10. Implementar worker e e-mails
  - Outbox no commit, seleção/deduplicação de destinatários, leases, retries e falhas auditadas.
  - Revalidar consentimento no envio; descadastro; templates sem endereço preciso ou destinatários expostos.
  - Critério: reinício retoma trabalho; falha do SMTP não reverte cadastro/pontos. R09.

- [x] 11. Implementar interface e administração
  - Telas do design, responsividade, rótulos acessíveis, estados vazios e feedback de conflitos.
  - Carteiras pessoal/institucional, benefícios, painel parceiro e validações administrativas.
  - Critério: fluxo completo pelo navegador sem uso manual do banco; testes de acesso horizontal. R01–R10.

- [x] 12. Validar consistência e concorrência
  - Implementar casos da matriz abaixo em MySQL real com conexões concorrentes.
  - Reconciliar saldos, verificar exclusividade, privacidade, rollback e idempotência após timeout.
  - Critério: todos os cenários críticos passam antes de deploy demonstrativo.

- [x] 13. Preparar deploy EC2
  - Infraestrutura reproduzível, IAM mínimo, MySQL local/EBS, S3 privado, TLS e serviços systemd.
  - Migração explícita, bootstrap do admin, backup externo, restore medido e rollback documentado.
  - Configurar remetente/provedor de e-mail e testar limites reais da conta.
  - Critério: portas de banco/app fechadas externamente; dados e fila persistem após reboot. R10.

- [x] 14. Preparar demonstração do hackathon
  - Seed somente demonstrativo de admin, ONG aprovada, pessoas, parceiro e benefícios.
  - Criar pet em risco, assumir/confirmar resgate, validar 25/40 pontos, concluir adoção sem pontos adicionais e trocar benefício.
  - Demonstrar variante normal sem ONG: 15 pontos ao publicador; mostrar extrato e e-mail de teste.
  - Não disparar seed em produção nem prometer prêmio de empresa sem acordo.

## Matriz mínima de aceite

| Caso | Resultado esperado | Requisito |
|---|---|---|
| Publicação normal | Publicador 5, ONG 0 | R03/R07 |
| Repetir publicação com mesma chave/corpo | Mesmo pet, saldo 5 | R03/R07 |
| Mesma chave, corpo diferente | 409, nenhuma criação adicional | R07 |
| ONG apenas assume | Sem bônus de desfecho | R04 |
| Resgate normal confirmado | Publicador total 15, ONG 15 | R04/R07 |
| Resgate em risco aprovado confirmado | Publicador total 25, ONG 40 | R06/R07 |
| Risco pendente na confirmação | Pet acolhido, só +5 disponíveis | R06 |
| Aprovar risco depois do resgate | Total 25/40, uma liquidação | R06/R07 |
| Rejeitar risco pendente | Total 15/15, uma liquidação | R06/R07 |
| Adoção direta normal sem ONG | Total 15 ao publicador, nenhuma ONG | R05/R07 |
| Adoção direta de risco sem ONG | Total 25 ao publicador, nenhuma ONG | R05/R07 |
| Adoção após resgate pontuado | Pontos não mudam | R05/R07 |
| Apenas aprovação de adoção | ADOPTION_PENDING, sem bônus | R05 |
| Duas ONGs assumem juntas | Um sucesso, um 409 | R04 |
| Dois pedidos aprovados juntos | Uma reserva, um conflito | R05 |
| Duas trocas para último item | Uma troca, estoque 0 | R08 |
| Duas trocas com saldo para uma | Uma troca, saldo não negativo | R08 |
| Repetir uso do voucher | Sem segundo consumo | R08 |
| Uso e expiração simultâneos | Uso ou restituição, nunca ambos | R08 |
| SMTP falha após publicação | Pet/pontos persistem, entrega retentável | R09 |
| Membro de ONG removido consulta carteira | 403/404, dados protegidos | R02/R10 |
| Fraude após pontos gastos | Estorno auditado, bloqueio de trocas | R07 |
| Restaurar backup em ambiente isolado | Saldos/extratos/mídia recuperáveis | R10 |

## Definition of Done

Requisitos rastreáveis, endpoints documentados, matriz crítica aprovada, fluxo web demonstrável, nenhum segredo em código/log, backup restaurado, papéis e privacidade verificados, deploy reproduzível e limitações da instância única registradas. Não chamar apenas CRUD de pets de MVP concluído: pontuação, adoção e troca de benefícios integram a entrega.
