# <h1 style="color: #107ACF">Verifly</h1>

<p>Nosso projeto do segundo período - TOP 1</p>

### ! Atenção !

- O arquivo de estilo variables.css irá conter cores e fontes que iremos utilizar em todo o projeto;
- Todos os arquivos de .html devem conter o link do arquivo variable.css para que haja padronização;
- Sigam o primeiro arquivo de template adicionado e nao foquem em mexer no menu;

#### <p style="color: #FE731F; font-style: italic">Caso tenham qualquer dúvida quanto ao projeto, questionem no grupo.</p>

## Buscas executadas na máquina local

O painel continua hospedado. O botão **Verificar voos agora** grava solicitações
na coleção `verificacoes` do mesmo Firestore usado pelas reservas e retorna HTTP
202. O servidor não importa nem executa o Playwright. Um worker nesta máquina
consulta a fila, abre o navegador, executa os buscadores de Azul/GOL e publica os
resultados no Firestore. O painel atualiza os dados automaticamente a cada cinco
segundos. LATAM continua sem buscador implementado.

### Servidor do painel

Instale `requirements.txt`, mantenha `FIREBASE_SERVICE_ACCOUNT_JSON` configurada
com a credencial do Firebase e publique este código pelo processo de deploy do
projeto. O servidor precisa ter acesso às coleções `reservas` e `verificacoes`.
Não execute `local_worker.py` no servidor. O Playwright e seus navegadores são
necessários apenas na máquina local.

### Máquina local (PowerShell)

Na pasta do projeto, execute uma vez:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-local.txt
.\.venv\Scripts\python.exe -m playwright install chromium
```

Em cada terminal onde for iniciar o worker, configure o caminho da sua chave
Firebase e execute:

```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS = (Resolve-Path '.\verifly-56717-firebase-adminsdk-fbsvc-3f1251030a.json').Path
.\.venv\Scripts\python.exe local_worker.py
```

Com a chave já presente nesta pasta, o atalho equivalente é
`.\start_worker.ps1`. Ele também aceita `-Headless` ou
`-CredentialsPath 'C:\caminho\outra-chave.json'`.

A chave deve apontar para o mesmo projeto Firebase do painel. O arquivo de chave
está ignorado pelo Git e não deve ser incluído em commits. Se a variável
`FIREBASE_SERVICE_ACCOUNT_JSON` também existir no terminal, ela tem precedência.

Deixe o terminal aberto e use **Verificar voos agora** no site. As linhas mostrarão
“Na fila” e depois “Verificação em andamento”. O navegador abre nesta máquina por
padrão; para ocultá-lo, configure `$env:VERIFLY_HEADLESS = '1'` antes de iniciar o
worker. Encerre com Ctrl+C.

Se a máquina estiver desligada ou o worker parado, as solicitações permanecem na
fila até ele ser iniciado. Uma execução interrompida pode ser retomada após cinco
minutos sem renovação. Cliques repetidos reutilizam a solicitação em andamento;
resultados antigos não sobrescrevem uma nova execução, reservas resolvidas ou
realizadas, nem trechos editados durante a consulta.

Para processar apenas a fila disponível e encerrar:

```powershell
.\.venv\Scripts\python.exe local_worker.py --once
```

O intervalo de consulta pode ser ajustado com `--poll-seconds 10`. O modo contínuo
é necessário para atender novas solicitações enquanto o painel estiver em uso.

### Verificação sem acessar o banco real

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node --check static/scripts/dashboard.js
```

## Histórico de reservas

A página `history.html` lista todas as reservas do Firestore e atualiza a cada
cinco segundos enquanto estiver visível. A busca aceita passageiro, localizador
e pasta. Os filtros de 30/60 dias e de período consideram a última movimentação
da reserva; os contadores refletem as reservas filtradas. Ao abrir uma reserva,
a linha do tempo exibe os eventos do mais recente para o mais antigo, com
paginação de 25 eventos e opção de carregar os anteriores.

Cadastro, atualização do cadastro, solicitação de verificação, resultado da
consulta, falha e mudanças manuais de status são registrados na subcoleção
`reservas/{id}/historico`. Cada evento contém data/hora e os dados anteriores e
posteriores, incluindo os horários consultados. O evento e a alteração da reserva
são gravados na mesma transação. Novas verificações preservam os eventos antigos.
O endpoint de leitura é `GET /api/reservas/{id}/historico`, com parâmetros
opcionais `limit` (1 a 100) e `cursor` retornado como `nextCursor`.

Reservas anteriores à implementação aparecem com sua situação atual. Não há
reconstrução de eventos antigos que não foram armazenados. Depois da publicação,
reinicie também o worker local com o código atualizado para que ele passe a
registrar os eventos de verificação.
