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

    if (!clone.querySelector('.btn-remove-segment')) {
        clone.querySelector('.segment-top').appendChild(createRemoveButton());
    }

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


/* ---------- Coleta e Validação dos dados do formulário ---------- */

function getSegmentsData() {
    return Array.from(segmentsList.querySelectorAll('.segment')).map((segment, index) => {
        const departureDate = segment.querySelector('[name="departure_date"]').value.trim();
        const departureHour = segment.querySelector('[name="departure_hour"]').value.trim();
        const arrivalDate = segment.querySelector('[name="arrival_date"]').value.trim();
        const arrivalHour = segment.querySelector('[name="arrival_hour"]').value.trim();

        return {
            order: index + 1,
            origin: segment.querySelector('[name="origin"]').value.trim().toUpperCase(),
            destination: segment.querySelector('[name="destination"]').value.trim().toUpperCase(),
            type: segment.querySelector('[name="type"]').value,
            departureOriginal: departureDate,
            departureHourOriginal: departureHour,
            arrivalOriginal: arrivalDate,
            arrivalHourOriginal: arrivalHour,
            company: segment.querySelector('[name="airline"]').value,
            urlReserve: segment.querySelector('[name="reserve_url"]').value.trim(),
            status: 'confirmed'
        };
    });
}

function validateSegmentsSchedule(stretches) {
    for (const stretch of stretches) {
        if (!stretch.departureHourOriginal || !stretch.arrivalHourOriginal) {
            alert(`Preencha os horários de partida e chegada do Trecho ${stretch.order}.`);
            return false;
        }

        const depDateTime = new Date(`${stretch.departureOriginal}T${stretch.departureHourOriginal}`);
        const arrDateTime = new Date(`${stretch.arrivalOriginal}T${stretch.arrivalHourOriginal}`);

        if (arrDateTime < depDateTime) {
            alert(`No Trecho ${stretch.order}, a data/horário de chegada não pode ser anterior à data/horário de partida.`);
            return false;
        }
    }
    return true;
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

    if (!validateSegmentsSchedule(reserveData.stretches)) {
        return;
    }

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