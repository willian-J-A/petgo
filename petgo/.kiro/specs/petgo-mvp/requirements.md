# Requirements Document — PetGo MVP

## Introduction

PetGo conecta pessoas, ONGs e empresas parceiras para registrar animais que precisam de resgate, acompanhar seu acolhimento e viabilizar adoção responsável. A participação gera pontos verificáveis que podem ser trocados por prêmios oferecidos por parceiros.

Stack definida: **Python + Flask + MySQL, executados em uma instância Amazon EC2**. Esta versão substitui os requisitos divergentes dos três pacotes de origem. O backend é um monólito modular; a interface web usa Jinja2 e CSS responsivo. Não há exigência de aplicativo mobile nativo.

## Decisões de produto adotadas nesta revisão

Estas decisões resolvem ambiguidades para permitir implementação; não representam confirmação posterior do solicitante.

1. Os pontos de risco **substituem** os pontos normais do desfecho. Os 5 pontos do cadastro permanecem cumulativos.
2. O bônus de desfecho ocorre uma única vez por pet: no primeiro resgate confirmado ou na adoção direta confirmada. A adoção posterior de animal já resgatado não gera novo bônus.
3. Quem publica recebe pontos na carteira pessoal. A ONG recebe pontos na carteira institucional, mesmo quando seu representante publica o pet. Os beneficiários e eventos ficam identificados separadamente.
4. O adotante final pode se cadastrar e solicitar adoção, mas não recebe pontos apenas por adotar: valor não definido pelo solicitante.
5. Risco exige evidência e validação administrativa antes do crédito do desfecho. Uma classificação pendente impede a liquidação do bônus, sem impedir o atendimento ao animal.
6. Na adoção direta sem ONG, apenas quem publicou recebe o bônus. Não se cria uma ONG fictícia para distribuir pontos.
7. Resgate significa retirada efetiva do animal da situação reportada. Assumir o atendimento não gera pontos.
8. Pontos não equivalem a dinheiro e não têm conversão monetária ou transferência no MVP. Não expiram no MVP; mudanças futuras exigem política explícita.

## Glossary

- Pessoa: conta autenticada capaz de publicar pets e manifestar interesse em adoção.
- ONG: organização com representantes autenticados e aprovação administrativa.
- Publicador: usuário que criou o registro original do pet; identidade imutável para pontuação.
- Responsável: pessoa ou ONG que atualmente acompanha o animal; não se confunde com publicador.
- Atendimento: ação de resgate ou adoção direta, sujeita a confirmação.
- Risco: ameaça concreta à integridade do animal, descrita e documentada; condição validada para a pontuação especial.
- Carteira: saldo e extrato de uma pessoa ou ONG.
- Lançamento: crédito ou débito imutável de pontos, vinculado a um evento.
- Resgate de prêmio: troca de pontos por um benefício; diferente de resgate de animal.
- Parceiro: empresa que disponibiliza benefícios e estoque; não recebe pontos automaticamente.

## Requirements

### R01 — Cadastro, autenticação e perfis

**User Story:** Como pessoa interessada em ajudar ou adotar, quero criar minha conta e informar minhas preferências.

1. QUANDO nome, e-mail, senha e cidade/UF válidos forem enviados, o sistema DEVE criar a conta e responder 201, sem retornar senha ou hash.
2. SE o e-mail normalizado já existir, o sistema DEVE responder 409 e não criar outra conta.
3. O sistema DEVE armazenar hash de senha, verificar credenciais e criar sessão autenticada; falhas de login DEVEM retornar mensagem genérica.
4. O sistema DEVE permitir atualizar telefone opcional, interesse em adoção, espécies, cidade/UF e consentimento para alertas por e-mail.
5. O sistema DEVE verificar a titularidade do e-mail antes de liberar publicação e troca de prêmios; login e consulta de perfil podem ocorrer antes.
6. O sistema DEVE permitir logout, recuperação de senha com token temporário de uso único e suspensão administrativa.
7. O sistema DEVE impedir que o cliente atribua papéis administrativos ou pontos a si mesmo.

### R02 — Cadastro e verificação de ONGs

**User Story:** Como representante de uma ONG, quero cadastrar a organização para assumir resgates e participar do programa.

1. QUANDO um usuário enviar nome da ONG, CNPJ, contato, endereço e dados de comprovação, o sistema DEVE criar ONG pendente e vínculo de representante.
2. O sistema DEVE validar dígitos verificadores e unicidade do CNPJ normalizado. Isso não substitui a verificação institucional administrativa.
3. SOMENTE administrador DEVE aprovar, rejeitar ou suspender uma ONG, com motivo e auditoria.
4. SOMENTE representante ativo de ONG aprovada DEVE agir em nome dela, consultar sua carteira e trocar seus pontos.
5. O sistema DEVE preservar a carteira institucional e o histórico quando um representante for removido.

### R03 — Publicação e consulta de pets

**User Story:** Como pessoa ou representante de ONG, quero registrar um animal que precisa de ajuda.

1. QUANDO um usuário ativo com e-mail verificado informar espécie, descrição, cidade/UF, localização, tipo de ajuda e ao menos uma foto válida, o sistema DEVE criar o pet no MySQL.
2. Nome pode ser apelido ou desconhecido; idade, porte e sexo podem ser desconhecidos. Espécie aceita `DOG`, `CAT`, `OTHER`; tipo de ajuda aceita `RESCUE`, `ADOPTION`, `TREATMENT`, `FOSTER`.
3. O estado inicial DEVE ser `NEEDS_RESCUE` para resgate, `SHELTERED` para tratamento/lar temporário ou `AVAILABLE` para adoção; nenhum cliente pode criar diretamente um pet adotado ou resgatado.
4. Localização de resgate DEVE incluir coordenadas válidas; para animais acolhidos, cidade/UF bastam. Endereço exato e coordenadas precisas DEVEM ficar restritos aos atores autorizados.
5. O sistema DEVE registrar publicador, responsável inicial, datas e histórico; o vínculo com ONG é opcional e exige representação ativa.
6. Na mesma transação do cadastro, o sistema DEVE creditar 5 pontos ao publicador e criar evento de notificação. Repetição da mesma requisição idempotente não pode duplicar pet nem pontos.
7. O sistema DEVE oferecer listas separadas para resgate e adoção, filtros combinados por espécie, porte, sexo, cidade/UF, tipo de ajuda e risco validado; paginação padrão 20 e máximo 100.
8. A lista de adoção DEVE conter somente animais `AVAILABLE`; a de resgate, `NEEDS_RESCUE` e `IN_RESCUE`, distinguindo disponibilidade de atendimento.
9. Alterações DEVEM ser restritas ao responsável autorizado ou administrador; o publicador sem responsabilidade mantém acesso ao acompanhamento, sem poder alterar custódia.
10. Exclusão DEVE ser lógica, preservar eventos, pontos e auditoria. Duplicatas e fraude DEVEM permitir moderação e estorno, nunca apagar o extrato.

### R04 — Resgate por ONG

**User Story:** Como ONG aprovada, quero assumir e concluir o atendimento de um pet.

1. QUANDO uma ONG aprovada assumir um pet `NEEDS_RESCUE`, o sistema DEVE mudar para `IN_RESCUE` e atribuir um único atendimento ativo.
2. SE duas ONGs tentarem assumir simultaneamente, apenas uma DEVE concluir; a outra recebe 409.
3. Assumir DEVE gerar histórico e aviso ao publicador, sem crédito de pontos.
4. QUANDO a ONG anexar evidência e declarar resgate realizado, o atendimento DEVE ficar `PENDING_CONFIRMATION`; o pet permanece `IN_RESCUE` até confirmação.
5. SOMENTE administrador ou publicador distinto do executor DEVE confirmar a realização. Se houver sobreposição de identidade/afiliação ou contestação, a confirmação DEVE ser administrativa.
6. Ao confirmar, o sistema DEVE definir `SHELTERED`, registrar `rescued_at`, manter a ONG como responsável e liquidar os pontos de R07, se risco estiver decidido.
7. Cancelamento antes de conclusão DEVE liberar o pet para `NEEDS_RESCUE`, sem pontos de desfecho. Reabertura posterior exige administrador e não restaura elegibilidade automaticamente.

### R05 — Adoção responsável e adoção direta

**User Story:** Como adotante, quero solicitar a adoção e acompanhar a confirmação da entrega.

1. Usuário ativo com e-mail verificado DEVE poder solicitar adoção de pet `AVAILABLE` ou adoção direta de pet `NEEDS_RESCUE`, com dados de contato e aceite de responsabilidade.
2. A solicitação direta NÃO DEVE marcar o animal como adotado nem bloquear atendimento urgente por ONG; conflito com resgate assumido DEVE exigir revisão do responsável/admin.
3. O sistema DEVE impedir pedidos ativos duplicados da mesma pessoa para o mesmo pet.
4. O responsável atual ou administrador DEVE revisar solicitações. Na adoção direta sem ONG, o publicador é o responsável inicial e pode aprovar candidato distinto de si.
5. A aprovação DEVE reservar o animal (`ADOPTION_PENDING`), manter só um pedido aprovado e encerrar os demais pedidos ativos com motivo. Aprovação NÃO gera pontos nem equivale à entrega.
6. A conclusão DEVE exigir confirmação de entrega pelo responsável e confirmação de recebimento pelo adotante; quando houver sobreposição de identidade, exigir decisão administrativa com evidência.
7. Na conclusão, o sistema DEVE gravar `ADOPTED`, adotante final, data, pedido `COMPLETED`, evento e eventual pontuação elegível em uma transação.
8. Cancelamento antes da entrega DEVE liberar a reserva e retornar ao estado de origem (`AVAILABLE` ou `NEEDS_RESCUE`), sem pontos de desfecho.
9. A adoção de animal já resgatado DEVE concluir normalmente, sem repetir bônus liquidado no resgate.

### R06 — Situação de risco

**User Story:** Como publicador, quero sinalizar urgência para priorizar ajuda com validação adequada.

1. O sistema DEVE armazenar `risk_status` (`NONE`, `PENDING`, `APPROVED`, `REJECTED`), descrição, evidência, decisor e instante da decisão.
2. O relato de risco DEVE ser possível na publicação ou antes da confirmação do desfecho. O estado pendente DEVE aparecer como relato ainda não verificado.
3. SOMENTE administrador DEVE aprovar ou rejeitar o risco, com justificativa; aprovação não pode ser feita pelo beneficiário do crédito.
4. Caso o resgate/adoção seja confirmado com risco pendente, o estado do pet DEVE avançar, mas a recompensa de desfecho DEVE aguardar a decisão.
5. Risco aprovado DEVE aplicar valores especiais; rejeitado ou ausente DEVE aplicar valores normais. Após liquidação, alteração exige processo administrativo de correção auditável.

### R07 — Gamificação e carteira

**User Story:** Como participante, quero receber e acompanhar pontos por ações comprovadas.

| Evento | Carteira do publicador | Carteira da ONG executora |
|---|---:|---:|
| Publicação válida | +5 | 0 |
| Primeiro resgate confirmado, sem risco aprovado | +10 | +15 |
| Primeiro resgate confirmado, risco aprovado | +20 | +40 |
| Adoção direta confirmada, sem ONG, sem risco aprovado | +10 | 0 |
| Adoção direta confirmada, sem ONG, risco aprovado | +20 | 0 |
| Adoção direta com ONG responsável participante e entrega confirmada | +10 normal / +20 risco | +15 normal / +40 risco |
| Adoção após resgate já pontuado | 0 | 0 |

1. O total do publicador DEVE ser 15 pontos no fluxo normal ou 25 no fluxo de risco, incluindo cadastro; a ONG recebe 15 ou 40, quando elegível.
2. O sistema DEVE criar no máximo um crédito de cadastro por pet e no máximo um crédito de desfecho por pet/carteira, independentemente de reenvio ou transição posterior.
3. O sistema DEVE considerar ONG elegível apenas quando aprovada e registrada como executora do resgate ou responsável participante da adoção; vínculo arbitrário na publicação não basta.
4. Toda alteração de saldo DEVE possuir lançamento com motivo, evento, regra/versão e beneficiário; pontos não podem ser editados por `PATCH` de perfil.
5. O crédito de desfecho DEVE depender de evidência e confirmação, sem pontuar simples mudança manual de status.
6. Cada carteira DEVE apresentar saldo disponível e extrato paginado. Pessoas não podem consultar extratos de outras pessoas; representantes consultam apenas suas ONGs.
7. Fraude confirmada DEVE gerar lançamento compensatório e bloqueio de novas trocas. Se os pontos já foram gastos, a carteira pode ficar negativa por estorno administrativo, nunca por compra normal.
8. Regras vigentes DEVEM ser versionadas e gravadas no evento de liquidação; alterações futuras não recalculam pontos antigos automaticamente.

### R08 — Empresas e prêmios

**User Story:** Como empresa parceira, quero oferecer benefícios; como participante, quero trocá-los usando pontos.

1. Administrador DEVE cadastrar/aprovar parceiros e vincular representantes. O parceiro DEVE gerenciar somente seus próprios benefícios; administrador pode moderar todos.
2. Prêmio DEVE ter nome, descrição, parceiro, custo inteiro positivo em pontos, estoque não negativo, período de validade, regras de uso e elegibilidade (`PERSON`, `NGO`, `BOTH`).
3. Apenas prêmios ativos, válidos e com estoque DEVE aparecer como disponíveis para troca.
4. A troca DEVE debitar saldo e estoque, criar pedido e voucher único na mesma transação; saldo insuficiente ou estoque esgotado DEVE responder 409 sem efeitos parciais.
5. Trocas simultâneas NÃO DEVEM produzir saldo negativo ou estoque negativo. Reenvio idempotente DEVE devolver a mesma troca.
6. O voucher DEVE ser visível somente ao titular, parceiro emissor autorizado e administrador; o parceiro DEVE validar/consumir o voucher uma única vez.
7. Troca NÃO DEVE prometer entrega automática: retirada, entrega ou desconto seguem as condições do parceiro exibidas antes do aceite.
8. Cancelamento de voucher não utilizado DEVE ocorrer por administrador; expiração DEVE ser processada pelo worker. Ambos DEVEM devolver pontos e estoque exatamente uma vez. Voucher utilizado não aceita cancelamento comum.
9. No MVP o administrador DEVE cadastrar ao menos um parceiro demonstrativo e benefícios com condições explícitas; não anunciar patrocínio real inexistente.

### R09 — Alertas por e-mail e notificações

**User Story:** Como ONG ou interessado em adoção, quero receber avisos relevantes de novos pets.

1. Ao publicar pet, o sistema DEVE agendar e-mails para ONGs aprovadas e pessoas interessadas em adoção, com e-mail verificado e consentimento ativo, respeitando cidade/UF e preferências; preferências de espécie vazias significam qualquer espécie.
2. Para destinatários que escolherem receber todos os locais, o sistema DEVE ignorar o filtro de cidade/UF. Todos podem receber alerta de cadastro, distinguindo resgate de disponibilidade para adoção.
3. QUANDO um pet passar para `AVAILABLE`, o sistema DEVE emitir aviso de disponibilidade aos interessados compatíveis, sem repetir o mesmo evento para o mesmo destinatário.
4. Avisos de atendimento, solicitação e decisão DEVE ir apenas aos envolvidos; e-mails não podem divulgar lista de destinatários ou localização precisa.
5. O envio DEVE ocorrer fora da requisição HTTP; falha do provedor NÃO DEVE desfazer cadastro, adoção, resgate ou pontos.
6. O sistema DEVE manter tentativa, status e erro sanitizado, repetir falhas temporárias e permitir reprocessar falhas finais administrativamente.
7. A interface DEVE permitir descadastro de alertas e mostrar estados de entrega honestos: aceitação pelo provedor não prova leitura ou entrega na caixa de entrada.

### R10 — Operação e segurança

1. A aplicação Flask, worker e MySQL DEVEM operar na mesma EC2 no MVP, sob processos separados e reinício automático; persistência em EBS, não em armazenamento efêmero.
2. MySQL DEVE aceitar somente conexões locais; as portas 3306 e do Gunicorn não podem ficar expostas à internet. HTTPS é obrigatório no endpoint público.
3. Segredos DEVEM vir de configuração protegida; AWS via IAM role de menor privilégio. Senhas, tokens, endereço preciso e documentos de comprovação não podem aparecer em logs ou listagens públicas.
4. Migrações DEVEM ser executadas explicitamente no deploy; não recriar tabelas no início de cada worker.
5. Upload DEVE validar conteúdo, extensão permitida, tamanho e autorização; limite proposto: 5 imagens JPEG/PNG/WebP de até 5 MB por pet. Documentos privados não podem usar a galeria pública.
6. O sistema DEVE ter controle de acesso por recurso, CSRF nos formulários e API autenticada por cookie, limitação de tentativas e registro de ações administrativas.
7. Backups DEVEM sair da EC2 e ter restauração demonstrada antes do aceite; o MVP não oferece alta disponibilidade, e a indisponibilidade da instância afeta aplicação e banco.
8. O sistema DEVE apresentar termos de uso, finalidade dos dados e opção de solicitar encerramento da conta; anonimização não pode apagar a trilha transacional necessária.

## Escopo posterior

Aplicativos nativos, chat, mapa em tempo real, pagamentos/doações, ranking público, integração automática com lojistas, resgate por pessoa independente com carteira de executor, múltiplas instâncias e RDS ficam fora do MVP. Tratamento e lar temporário são informações e estados do animal, sem novos bônus.
