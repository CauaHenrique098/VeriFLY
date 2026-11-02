const API_URL = '/api/reservas';

const monitoringBody = document.getElementById('monitoring-body');
const btnCheckAll = document.getElementById('btn-check-all');
const filterLabel = document.getElementById('filter-label');
const cards = document.querySelectorAll('[data-filter]');

// Status que o comparador pode reclassificar (resolvido/realizado são manuais)
const COMPARABLE_STATUS = ['pending', 'high_priority', 'low_priority', 'confirmed'];

const STATUS_CONFIG = {
    high_priority: { label: 'Alterado - Alta prioridade', dot: 'red', badge: 'badge-red' },
    low_priority: { label: 'Alterado - Baixa prioridade', dot: 'yellow', badge: 'badge-yellow' },
    confirmed: { label: 'Sem alteração', dot: 'green', badge: 'badge-green' },
    solved: { label: 'Resolvido', dot: 'blue', badge: 'badge-blue' },
    completed: { label: 'Realizado', dot: 'gray', badge: 'badge-gray' },
    pending: { label: 'Aguardando verificação', dot: 'gray', badge: 'badge-gray' }
};

// Ordem de exibição na tabela
const STATUS_ORDER = ['high_priority', 'low_priority', 'pending', 'confirmed', 'solved', 'completed'];

const AIRLINES = { azul: 'Azul', latam: 'LATAM', gol: 'GOL' };

let reserves = [];
let activeFilter = null;


/* ---------- Utilidades ---------- */

function escapeHtml(text) {
    return String(text ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

// '2026-10-07T13:30' -> '07/10/2026 · 13:30'
function formatDateTime(value) {
    if (!value) return '-';

    const [day, hour] = value.split('T');
    const [year, month, dayOfMonth] = day.split('-');

    return `${dayOfMonth}/${month}/${year}` + (hour ? ` · ${hour.slice(0, 5)}` : '');
}

function replaceReserve(updated) {
    const index = reserves.findIndex(reserve => reserve.id === updated.id);

    if (index >= 0) {
        reserves[index] = updated;
    } else {
        reserves.push(updated);
    }
}


/* ---------- Renderização ---------- */

function renderCounters() {
    document.querySelectorAll('[data-count]').forEach(counter => {
        const status = counter.dataset.count;
        counter.textContent = reserves.filter(reserve => reserve.status === status).length;
    });
}

function buildRow(reserve) {
    const config = STATUS_CONFIG[reserve.status] || STATUS_CONFIG.pending;
    const stretches = reserve.stretches || [];
    const first = stretches[0] || {};

    const route = stretches.length
        ? [first.origin, ...stretches.map(stretch => stretch.destination)].join(' ➔ ')
        : '-';

    // Detalhe do que mudou (só para voos alterados ou já resolvidos)
    let detail = '';
    if (['high_priority', 'low_priority', 'solved'].includes(reserve.status)) {
        detail = (reserve.segmentResults || [])
            .filter(result => result.status === 'changed')
            .map(result => `<span class="change-detail">${escapeHtml(result.origin)} ➔ ${escapeHtml(result.destination)}: novo embarque ${formatDateTime(result.newDeparture)}</span>`)
            .join('');
    }

    if (reserve.lastCheckError) {
        detail += `<span class="change-detail error">Falha na verificação: ${escapeHtml(reserve.lastCheckError)}</span>`;
    }

    const canSolve = ['high_priority', 'low_priority'].includes(reserve.status);
    const canComplete = reserve.status !== 'completed';

    const buttons = [
        '<button class="btn-details">Ver detalhes</button>',
        reserve.status === 'low_priority' ? '<button class="btn-postpone">Adiar contato</button>' : '',
        canSolve ? `<button class="btn-solved" data-action="solved" data-id="${escapeHtml(reserve.id)}">RESOLVIDO</button>` : '',
        canComplete ? `<button class="btn-completed" data-action="completed" data-id="${escapeHtml(reserve.id)}">REALIZADO</button>` : ''
    ].join('');

    return `
        <tr>
            <td class="dot"><span class="status-dot ${config.dot}"></span></td>
            <td>
                <span class="client-name">${escapeHtml(reserve.name)}</span>
                <span class="client-pnr">PNR: ${escapeHtml(reserve.codeReserve)}</span>
            </td>
            <td>${escapeHtml(AIRLINES[first.company] || first.company || '-')}</td>
            <td>${escapeHtml(route)}</td>
            <td>${formatDateTime(first.departureOriginal)}</td>
            <td>
                <span class="badge ${config.badge}">${config.label}</span>
                ${detail}
            </td>
            <td><div class="actions-cell">${buttons}</div></td>
        </tr>`;
}

function renderTable() {
    const visible = reserves
        .filter(reserve => !activeFilter || reserve.status === activeFilter)
        .sort((a, b) => {
            const byStatus = STATUS_ORDER.indexOf(a.status) - STATUS_ORDER.indexOf(b.status);
            if (byStatus !== 0) return byStatus;

            const dateA = (a.stretches?.[0]?.departureOriginal) || '';
            const dateB = (b.stretches?.[0]?.departureOriginal) || '';
            return dateA.localeCompare(dateB);
        });

    if (!visible.length) {
        monitoringBody.innerHTML = '<tr><td colspan="7" class="empty-row">Nenhuma reserva nesta lista.</td></tr>';
        return;
    }

    monitoringBody.innerHTML = visible.map(buildRow).join('');
}

function render() {
    renderCounters();
    renderTable();

    cards.forEach(card => {
        card.querySelector('.card').classList.toggle('card-active', card.dataset.filter === activeFilter);
    });

    filterLabel.textContent = activeFilter
        ? `Mostrando: ${STATUS_CONFIG[activeFilter].label} (clique no card de novo para limpar)`
        : '';
}


/* ---------- Carregar reservas ---------- */

async function loadReserves() {
    try {
        const response = await fetch(API_URL);

        if (!response.ok) {
            throw new Error('Erro ao buscar as reservas (status ' + response.status + ')');
        }

        reserves = await response.json();
        render();

    } catch (error) {
        console.error(error);
        monitoringBody.innerHTML = '<tr><td colspan="7" class="empty-row">Não foi possível carregar as reservas.</td></tr>';
    }
}


/* ---------- Filtro pelos cards ---------- */

cards.forEach(card => {
    card.addEventListener('click', (event) => {
        event.preventDefault();

        const filter = card.dataset.filter;
        activeFilter = activeFilter === filter ? null : filter;
        render();
    });
});


/* ---------- Botões RESOLVIDO e REALIZADO ---------- */

monitoringBody.addEventListener('click', async (event) => {
    const button = event.target.closest('[data-action]');
    if (!button) return;

    const message = button.dataset.action === 'solved'
        ? 'Marcar este voo como RESOLVIDO?'
        : 'Marcar este voo como REALIZADO?';

    if (!confirm(message)) return;

    button.disabled = true;

    try {
        const response = await fetch(`${API_URL}/${encodeURIComponent(button.dataset.id)}/status`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: button.dataset.action })
        });

        if (!response.ok) {
            const body = await response.json().catch(() => ({}));
            throw new Error(body.erro || 'Erro ao atualizar o status (status ' + response.status + ')');
        }

        replaceReserve(await response.json());
        render(); // contadores e listas são recalculados

    } catch (error) {
        console.error(error);
        alert(error.message);
        button.disabled = false;
    }
});


/* ---------- Verificar voos (chama o comparador, uma reserva por vez) ---------- */

btnCheckAll.addEventListener('click', async () => {
    const targets = reserves.filter(reserve => COMPARABLE_STATUS.includes(reserve.status));

    if (!targets.length) {
        alert('Não há reservas para verificar.');
        return;
    }

    btnCheckAll.disabled = true;

    try {
        for (let index = 0; index < targets.length; index++) {
            btnCheckAll.textContent = `Verificando ${index + 1}/${targets.length}...`;

            try {
                const response = await fetch(`${API_URL}/${encodeURIComponent(targets[index].id)}/comparar`, { method: 'POST' });

                if (response.ok) {
                    replaceReserve(await response.json());
                    render();
                }
            } catch (error) {
                console.error(error); // segue para a próxima reserva
            }
        }
    } finally {
        btnCheckAll.disabled = false;
        btnCheckAll.textContent = 'Verificar voos agora';
    }
});


loadReserves();
