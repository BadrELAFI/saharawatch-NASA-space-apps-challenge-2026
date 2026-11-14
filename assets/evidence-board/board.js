export default function({data, parentElement, setStateValue}) {
    const root = parentElement.querySelector('.evidence-board-root');
    root.replaceChildren();
    const state = structuredClone(data.board);
    const cards = new Map(data.cards.map(card => [card.id, card]));
    const elements = new Map();
    const ns = 'http://www.w3.org/2000/svg';
    let source = null, dragging = null;
    const el = (tag, className, text) => {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    };
    const svg = (tag, attributes) => {
        const node = document.createElementNS(ns, tag);
        for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
        return node;
    };
    const save = () => {
        status.textContent = 'Saving board…';
        setStateValue('board', structuredClone(state));
    };
    const toolbar = el('div', 'board-toolbar');
    const label = el('label', '', 'Relationship');
    const relation = el('select');
    relation.setAttribute('aria-label', 'Evidence relationship');
    for (const [value, text] of Object.entries(data.relations)) {
        const option = el('option', '', text); option.value = value; relation.append(option);
    }
    relation.value = parentElement._boardRelation || 'supports';
    relation.onchange = () => {parentElement._boardRelation = relation.value;};
    label.append(relation); toolbar.append(label);
    const cancel = el('button', '', 'Cancel connection'); cancel.hidden = true;
    toolbar.append(cancel); root.append(toolbar);
    const status = el('p', 'board-status', data.cards.length
        ? 'Board saved in this session. Drag a heading to move a clue; red pins lock it in place.'
        : 'Pin your first finding above to start connecting the evidence.');
    status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite'); root.append(status);
    const viewport = el('div', 'board-scroll');
    viewport.setAttribute('aria-label', 'Scrollable cork evidence board'); viewport.tabIndex = 0;
    const canvas = el('div', 'board-canvas');
    const strings = svg('svg', {class:'board-strings', 'aria-hidden':'true'});
    canvas.append(strings); viewport.append(canvas); root.append(viewport);
    const connectionList = el('ul', 'connection-list');
    connectionList.setAttribute('aria-label', 'Evidence connections'); root.append(connectionList);

    const number = id => String(cards.get(id).number).padStart(2, '0');
    const cancelConnection = () => {
        source = null; cancel.hidden = true;
        for (const node of elements.values()) node.classList.remove('is-source');
        status.textContent = 'Connection cancelled. Your evidence is unchanged.';
    };
    cancel.onclick = cancelConnection;
    root.addEventListener('keydown', event => {if (event.key === 'Escape') cancelConnection();});

    function drawStrings() {
        strings.replaceChildren(); connectionList.replaceChildren();
        for (const edge of state.connections) {
            const a = state.positions[edge.source], b = state.positions[edge.target];
            const x1 = a.x+140, y1 = a.y+5, x2 = b.x+140, y2 = b.y+5;
            const mx = (x1+x2)/2, my = Math.max(20, Math.min(y1,y2)-35);
            const path = `M ${x1} ${y1} Q ${x1} ${my} ${mx} ${my} Q ${x2} ${my} ${x2} ${y2}`;
            strings.append(svg('path', {d:path, class:'string-shadow'}));
            const line = svg('path', {d:path, class:'string-line'});
            if (edge.relation === 'challenges') line.setAttribute('stroke-dasharray', '9 5');
            if (edge.relation === 'context') line.setAttribute('stroke-dasharray', '2 5');
            strings.append(line);
            const tx = mx, ty = my;
            const text = `${number(edge.source)} → ${number(edge.target)} · ${data.relations[edge.relation]}`;
            const width = Math.max(160, text.length*6);
            strings.append(svg('rect', {x:tx-width/2, y:ty-12, width, height:24, rx:4, class:'string-label'}));
            const caption = svg('text', {x:tx, y:ty+4, class:'string-text'}); caption.textContent = text; strings.append(caption);
            const item = el('li', '', `Clue ${number(edge.source)} → Clue ${number(edge.target)} · ${data.relations[edge.relation]}`);
            const remove = el('button', '', 'Remove');
            remove.setAttribute('aria-label', `Remove connection from clue ${number(edge.source)} to clue ${number(edge.target)}`);
            remove.onclick = () => {state.connections = state.connections.filter(other => other !== edge); drawStrings(); save();};
            item.append(remove); connectionList.append(item);
        }
    }

    function place(id) {
        const card = elements.get(id), position = state.positions[id];
        card.style.left = `${position.x}px`; card.style.top = `${position.y}px`;
        card.classList.toggle('is-pinned', position.pinned);
        const pin = card.querySelector('.card-pin');
        pin.setAttribute('aria-pressed', String(position.pinned));
        pin.setAttribute('aria-label', `${position.pinned ? 'Unpin' : 'Pin'} clue ${number(id)}`);
        pin.title = position.pinned ? 'Unpin to move this clue' : 'Pin this clue in place';
        card.querySelector('.pin-status').textContent = position.pinned ? 'PINNED' : 'MOVABLE';
        canvas.style.height = `${Math.max(800, ...Object.entries(state.positions).map(([key, p]) => p.y+(elements.get(key)?.offsetHeight || 360)+80))}px`;
    }

    function sparkline(rows) {
        const chart = svg('svg', {viewBox:'0 0 244 48', class:'card-sparkline', role:'img', 'aria-label':'Pinned annual rainfall timeline; gaps indicate missing observations'});
        const valid = rows.filter(row => Number.isFinite(row.precipitation_mm));
        if (!valid.length) return chart;
        const years = rows.map(row => row.year), first = Math.min(...years), last = Math.max(...years);
        const values = valid.map(row => row.precipitation_mm), low = Math.min(...values), span = Math.max(1, Math.max(...values)-low);
        let path = '', previous = null;
        for (const row of rows) {
            if (!Number.isFinite(row.precipitation_mm)) {previous = null; continue;}
            const x = 3+238*(row.year-first)/Math.max(1,last-first), y = 44-40*(row.precipitation_mm-low)/span;
            path += `${previous !== null && row.year === previous+1 ? 'L' : 'M'}${x},${y} `;
            previous = row.year;
        }
        chart.append(svg('path', {d:path, stroke:'#41694e', 'stroke-width':2, fill:'none'}));
        return chart;
    }

    function beginConnection(id) {
        if (!source) {
            source = id; cancel.hidden = false; elements.get(id).classList.add('is-source');
            status.textContent = `Clue ${number(id)} selected. Press Connect on another clue to add “${data.relations[relation.value]}”.`;
        } else if (source === id) {
            cancelConnection();
        } else {
            state.connections = state.connections.filter(edge => !(edge.source === source && edge.target === id));
            state.connections.push({source, target:id, relation:relation.value});
            const message = `Connected clue ${number(source)} to clue ${number(id)}.`;
            cancelConnection(); status.textContent = message; drawStrings(); save();
        }
    }

    for (const card of data.cards) {
        const node = el('article', 'evidence-card'); node.dataset.clueId = card.id;
        node.setAttribute('aria-label', `Clue ${number(card.id)}: ${card.location}`);
        const pin = el('button', 'card-pin'); pin.onclick = () => {
            const position = state.positions[card.id]; position.pinned = !position.pinned;
            place(card.id); status.textContent = `Clue ${number(card.id)} ${position.pinned ? 'pinned in place' : 'unlocked for moving'}.`; save();
        };
        node.append(pin);
        const grip = el('div', 'card-grip'); grip.tabIndex = 0; grip.setAttribute('role', 'button');
        grip.setAttribute('aria-label', `Move clue ${number(card.id)} with arrow keys; Space toggles pin`);
        const eyebrow = el('div', 'card-eyebrow');
        eyebrow.append(el('span', '', `EXHIBIT ${number(card.id)}`), el('span', 'pin-status'));
        grip.append(eyebrow, el('h4', '', card.location), el('div', 'card-period', card.period));
        node.append(grip, el('p', 'card-hypothesis', card.hypothesis));
        node.append(sparkline(Array.isArray(card.annual_data) ? card.annual_data : []));
        node.append(el('p', 'card-stat', `${card.trend_mm_decade} mm/decade · p = ${card.p_value}`));
        node.append(el('p', 'card-assessment', card.assessment));
        const details = el('details', 'card-details'); details.append(el('summary', '', 'Notes, uncertainty & source'));
        details.append(el('div', 'card-detail-text', [card.notes || 'No field notes recorded.',
            `Assessment: ${card.assessment}`, `Baseline: ${card.baseline}`, `Method: ${card.inference_method}`,
            `95% slope interval: ${card.confidence_interval}`, `Country weighting: ${card.country_weighting}`,
            `Source: ${card.source}`, `SHA-256: ${card.source_sha256}`].join('\n\n')));
        details.ontoggle = () => place(card.id); node.append(details);
        const connect = el('button', 'card-connect', 'Connect');
        connect.setAttribute('aria-label', `Connect clue ${number(card.id)}`);
        connect.onclick = () => beginConnection(card.id); node.append(connect);
        canvas.append(node); elements.set(card.id, node);

        grip.onpointerdown = event => {
            if (event.button !== 0) return;
            if (state.positions[card.id].pinned) {status.textContent = 'Unpin this clue before moving it.'; return;}
            event.preventDefault(); grip.setPointerCapture(event.pointerId);
            dragging = {id:card.id, pointer:event.pointerId, x:event.clientX, y:event.clientY,
                left:viewport.scrollLeft, top:viewport.scrollTop, original:{...state.positions[card.id]}};
            node.classList.add('is-dragging');
        };
        grip.onpointermove = event => {
            if (!dragging || dragging.id !== card.id || dragging.pointer !== event.pointerId) return;
            const bounds = viewport.getBoundingClientRect();
            if (event.clientX > bounds.right-35) viewport.scrollLeft += 15;
            if (event.clientX < bounds.left+35) viewport.scrollLeft -= 15;
            if (event.clientY > bounds.bottom-35) viewport.scrollTop += 15;
            if (event.clientY < bounds.top+35) viewport.scrollTop -= 15;
            const position = state.positions[card.id];
            position.x = Math.max(20, Math.min(900, dragging.original.x+event.clientX-dragging.x+viewport.scrollLeft-dragging.left));
            position.y = Math.max(20, Math.min(12000, dragging.original.y+event.clientY-dragging.y+viewport.scrollTop-dragging.top));
            place(card.id); drawStrings();
        };
        const finish = event => {
            if (!dragging || dragging.id !== card.id || dragging.pointer !== event.pointerId) return;
            if (event.type === 'pointercancel') state.positions[card.id] = dragging.original;
            dragging = null; node.classList.remove('is-dragging'); place(card.id); drawStrings(); save();
        };
        grip.onpointerup = finish; grip.onpointercancel = finish;
        grip.onkeydown = event => {
            const position = state.positions[card.id];
            if (event.key === ' ') {event.preventDefault(); pin.click(); return;}
            if (!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key)) return;
            event.preventDefault();
            if (position.pinned) {status.textContent = 'Unpin this clue before moving it.'; return;}
            const step = event.shiftKey ? 40 : 12;
            if (event.key === 'ArrowLeft') position.x = Math.max(20, position.x-step);
            if (event.key === 'ArrowRight') position.x = Math.min(900, position.x+step);
            if (event.key === 'ArrowUp') position.y = Math.max(20, position.y-step);
            if (event.key === 'ArrowDown') position.y = Math.min(12000, position.y+step);
            place(card.id); drawStrings(); save();
        };
    }
    if (!data.cards.length) {
        const empty = el('div', 'board-empty');
        empty.append(el('strong', '', 'Every case starts with a clue.'),
            el('p', '', 'Pin an observation from the notebook above. Your evidence will appear here, ready to move, pin, and connect.'));
        canvas.append(empty);
    }
    for (const id of elements.keys()) place(id);
    drawStrings();
    const scroll = parentElement._boardScroll;
    if (scroll) {viewport.scrollLeft = scroll.left; viewport.scrollTop = scroll.top;}
    const focus = parentElement._boardFocus;
    if (focus) elements.get(focus.id)?.querySelector(focus.selector)?.focus({preventScroll:true});
    return () => {
        parentElement._boardScroll = {left:viewport.scrollLeft, top:viewport.scrollTop};
        const active = parentElement.activeElement;
        const card = active?.closest('.evidence-card');
        const selector = active?.matches('.card-grip') ? '.card-grip' : active?.matches('.card-pin') ? '.card-pin' : null;
        parentElement._boardFocus = card && selector ? {id:card.dataset.clueId, selector} : null;
    };
}
