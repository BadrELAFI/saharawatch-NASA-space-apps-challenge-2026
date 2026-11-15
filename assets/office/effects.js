export default function({data, parentElement}) {
    const root = parentElement.querySelector('.office-effects');
    const engine = window.saharaOffice ??= {context:null, master:null, plays:0, lastKind:null};
    engine.enabled = data.enabled;
    root.dataset.ready = 'true';
    root.dataset.sound = data.enabled ? 'enabled' : 'muted';
    if (engine.master) engine.master.gain.value = data.enabled ? .12 : 0;
    const changed = new WeakMap();
    function sound(kind) {
        if (!engine.enabled) return;
        try {
            const Audio = window.AudioContext || window.webkitAudioContext;
            if (!Audio) return;
            if (!engine.context) {
                engine.context = new Audio();
                engine.master = engine.context.createGain();
                engine.master.gain.value = .12;
                engine.master.connect(engine.context.destination);
            }
            const ctx=engine.context;
            ctx.resume().then(() => {
                if (!engine.enabled) return;
                const duration=kind === 'paper' ? .22 : kind === 'pencil' ? .09 : .14;
                const buffer=ctx.createBuffer(1,Math.ceil(ctx.sampleRate*duration),ctx.sampleRate);
                const values=buffer.getChannelData(0);
                for (let i=0;i<values.length;i++) values[i]=(Math.random()*2-1)*(1-i/values.length);
                const noise=ctx.createBufferSource(); noise.buffer=buffer;
                const filter=ctx.createBiquadFilter(); filter.type='bandpass';
                filter.frequency.value=kind === 'paper' ? 1300 : kind === 'pencil' ? 2600 : 220;
                filter.Q.value=kind === 'pencil' ? 1.3 : .6;
                const gain=ctx.createGain(); gain.gain.setValueAtTime(.001,ctx.currentTime);
                gain.gain.linearRampToValueAtTime(.5,ctx.currentTime+.012);
                gain.gain.exponentialRampToValueAtTime(.001,ctx.currentTime+duration);
                noise.connect(filter).connect(gain).connect(engine.master); noise.start();
                if (kind === 'stamp') {
                    const thud=ctx.createOscillator(), envelope=ctx.createGain();
                    thud.frequency.setValueAtTime(115,ctx.currentTime);
                    thud.frequency.exponentialRampToValueAtTime(55,ctx.currentTime+.12);
                    envelope.gain.setValueAtTime(.7,ctx.currentTime);
                    envelope.gain.exponentialRampToValueAtTime(.001,ctx.currentTime+.13);
                    thud.connect(envelope).connect(engine.master);thud.start();thud.stop(ctx.currentTime+.14);
                }
                engine.plays++;engine.lastKind=kind;
                noise.onended=()=>{noise.disconnect();filter.disconnect();gain.disconnect();};
            }).catch(()=>{});
        } catch (_) { /* Audio is optional; the investigation remains usable. */ }
    }
    function click(event) {
        const button=event.target.closest?.('button');
        if (!button || button.disabled) return;
        const folder=button.closest('[class*="st-key-desk_open_"], [class*="st-key-preset_"]');
        const label=button.textContent.trim();
        if (folder) {
            sound('paper');
            const file=folder.closest('[class*="st-key-file_case_"]')?.querySelector('.file-folder');
            if (!file || file.classList.contains('is-open') || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
            document.querySelectorAll('.file-folder.is-opening').forEach(node=>node.classList.remove('is-opening'));
            file.classList.add('is-opening');
        } else if (/^(Save investigation|Finish quiz)/.test(label)) {
            sound('stamp');
        } else if (/^(Pin |＋ Pin|Check my answer)/.test(label)) {
            sound('pencil');
        } else if (/^(Open quiz|Investigate this comparison)/.test(label)) sound('paper');
    }
    function focus(event) {
        if (event.target.matches?.('textarea')) changed.set(event.target,event.target.value);
    }
    function blur(event) {
        const node=event.target;
        if (!node.matches?.('textarea') || !changed.has(node) || changed.get(node) === node.value) return;
        sound('pencil');
        const wrapper=node.closest('[data-testid="stElementContainer"]');
        wrapper?.classList.add('pencil-written');
        if (wrapper) setTimeout(()=>wrapper.classList.remove('pencil-written'),600);
    }
    document.addEventListener('click',click,true);
    document.addEventListener('focusin',focus,true);
    document.addEventListener('focusout',blur,true);
    return () => {
        document.removeEventListener('click',click,true);
        document.removeEventListener('focusin',focus,true);
        document.removeEventListener('focusout',blur,true);
    };
}
