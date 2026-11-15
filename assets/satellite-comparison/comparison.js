export default function({data, parentElement, setStateValue}) {
    const root = parentElement.querySelector('.satellite-comparison-root');
    root.replaceChildren();
    root.dataset.savedPosition = String(data.position);
    root.dataset.savedGrid = String(data.show_grid);
    const make = (tag, className, text) => {
        const node = document.createElement(tag);
        node.className = className;
        if (text) node.textContent = text;
        return node;
    };
    const frame = make('div', 'satellite-frame');
    frame.setAttribute('aria-label', 'Aligned satellite images of the Casablanca region');
    for (const [index, image] of data.images.entries()) {
        const img = make('img', index === 0 ? 'satellite-before' : 'satellite-after');
        img.src = image.src;
        img.alt = `${image.platform} MODIS true-color image, ${image.date}`;
        img.draggable = false;
        frame.append(img);
    }
    const overlay = make('div', 'satellite-grid');
    // SVG is generated solely from validated, numeric geographic coordinates.
    overlay.innerHTML = data.grid_svg;
    frame.append(overlay);
    const before = make('span', 'satellite-date satellite-date-before', `BEFORE · ${data.images[0].date}`);
    const after = make('span', 'satellite-date satellite-date-after', `AFTER · ${data.images[1].date}`);
    const divider = make('div', 'satellite-divider');
    const handle = make('span', 'satellite-handle', '↔');
    divider.append(handle);
    frame.append(before, after, divider);
    const label = make('label', 'satellite-slider-label', 'Reveal the earlier image');
    const slider = make('input', 'satellite-slider');
    slider.type = 'range'; slider.min = '0'; slider.max = '100'; slider.step = '1';
    slider.setAttribute('aria-label', 'Reveal the earlier satellite image');
    const status = make('output', 'satellite-output');
    const controls = make('div', 'satellite-controls');
    const gridLabel = make('label', 'satellite-grid-label');
    const gridToggle = make('input', 'satellite-grid-toggle');
    gridToggle.type = 'checkbox'; gridToggle.checked = data.show_grid;
    gridLabel.append(gridToggle, document.createTextNode('Show GPCP rainfall cells (2.5°)'));
    gridToggle.onchange = () => {
        overlay.hidden = !gridToggle.checked;
        setStateValue('show_grid', gridToggle.checked);
    };
    overlay.hidden = !gridToggle.checked;
    label.append(slider);
    controls.append(label, status, gridLabel);
    root.append(frame, controls);
    function draw(value) {
        value = Math.max(0, Math.min(100, Math.round(value)));
        slider.value = value;
        frame.style.setProperty('--reveal', `${value}%`);
        status.value = `${value}% before / ${100-value}% after`;
        slider.setAttribute('aria-valuetext', `${value} percent earlier image revealed`);
    }
    draw(data.position);
    slider.oninput = () => draw(Number(slider.value));
    slider.onchange = () => setStateValue('position', Number(slider.value));
    function revealAt(event) {
        const bounds = frame.getBoundingClientRect();
        draw(100*(event.clientX-bounds.left)/bounds.width);
    }
    frame.onpointerdown = event => {
        if (event.button !== 0) return;
        event.preventDefault(); frame.setPointerCapture(event.pointerId); revealAt(event);
    };
    frame.onpointermove = event => {
        if (frame.hasPointerCapture(event.pointerId)) revealAt(event);
    };
    frame.onpointerup = event => {
        if (!frame.hasPointerCapture(event.pointerId)) return;
        revealAt(event); frame.releasePointerCapture(event.pointerId);
        setStateValue('position', Number(slider.value));
    };
    if (parentElement._satelliteFocus === 'slider') slider.focus({preventScroll:true});
    if (parentElement._satelliteFocus === 'grid') gridToggle.focus({preventScroll:true});
    return () => {
        const active = parentElement.activeElement;
        parentElement._satelliteFocus = active === slider ? 'slider' : active === gridToggle ? 'grid' : null;
    };
}
