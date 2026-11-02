const form = document.getElementById('new-reserve-form');
const segmentsList = document.getElementById('segments-list');
const btnAddSegment = document.getElementById('btn-add-segment');
const btnRegister = form.querySelector('.btn-register');

const API_URL = '/api/reservas';


/* ---------- Trechos (adicionar / remover) ---------- */

function updateSegments() {
    const segments = segmentsList.querySelectorAll('.segment');

    segments.forEach((segment, index) => {
        segment.querySelector('.segment-tag').textContent = 'TRECHO ' + (index + 1);

        const btnRemove = segment.querySelector('.btn-remove-segment');

        // O primeiro trecho nunca pode ser removido
        if (index === 0 && btnRemove) {
            btnRemove.remove();
        }
    });
}

function createRemoveButton() {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'btn-remove-segment';
    btn.setAttribute('aria-label', 'Remover trecho');
    btn.innerHTML = '&times;';
    return btn;
}

function addSegment() {
    const clone = segmentsList.querySelector('.segment').cloneNode(true);

    clone.querySelectorAll('input').forEach(input => input.value = '');
    clone.querySelectorAll('select').forEach(select => select.selectedIndex = 0);

    clone.querySelector('.segment-top').appendChild(createRemoveButton());

    segmentsList.appendChild(clone);
    updateSegments();
}

function resetSegments() {
    const segments = segmentsList.querySelectorAll('.segment');
    segments.forEach((segment, index) => {
        if (index > 0) segment.remove();
    });
    updateSegments();
}

btnAddSegment.addEventListener('click', addSegment);

segmentsList.addEventListener('click', (event) => {
    const btnRemove = event.target.closest('.btn-remove-segment');
    if (!btnRemove) return;

    btnRemove.closest('.segment').remove();
    updateSegments();
});


/* ---------- Coleta dos dados do formulário ---------- */

function getSegmentsData() {
    return Array.from(segmentsList.querySelectorAll('.segment')).map((segment, index) => ({
        order: index + 1,
        origin: segment.querySelector('[name="origin"]').value.trim().toUpperCase(),
        destination: segment.querySelector('[name="destination"]').value.trim().toUpperCase(),
        type: segment.querySelector('[name="type"]').value,
        departureOriginal: segment.querySelector('[name="departure_date"]').value,
        arrivalOriginal: segment.querySelector('[name="arrival_date"]').value,
        company: segment.querySelector('[name="airline"]').value,
        urlReserve: segment.querySelector('[name="reserve_url"]').value.trim()
    }));
}

function getReserveData() {
    return {
        name: form.elements['client_name'].value.trim(),
        codeReserve: form.elements['reserve_pnr'].value.trim().toUpperCase(),
        telefone: form.elements['client_phone'].value.trim(),
        folder: form.elements['folder'].value.trim(),
        stretches: getSegmentsData()
    };
}


/* ---------- Envio para o backend (que grava no Firestore) ---------- */

form.addEventListener('submit', async (event) => {
    event.preventDefault();

    const reserveData = getReserveData();

    btnRegister.disabled = true;
    btnRegister.textContent = 'Cadastrando...';

    try {
        const response = await fetch(API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(reserveData)
        });

        if (!response.ok) {
            throw new Error('Erro ao salvar a reserva (status ' + response.status + ')');
        }

        alert('Reserva cadastrada com sucesso!');
        form.reset();
        resetSegments();

    } catch (error) {
        console.error(error);
        alert('Não foi possível cadastrar a reserva. Tente novamente.');

    } finally {
        btnRegister.disabled = false;
        btnRegister.textContent = 'Cadastrar e Monitorar';
    }
});
