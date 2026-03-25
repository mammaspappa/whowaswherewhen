const Timeline = (() => {
    let slider, label, playBtn;
    let startDay, endDay;
    let playing = false;
    let playInterval = null;
    let onDateChange = null;

    function init(sliderId, labelId, playBtnId, callback) {
        slider = document.getElementById(sliderId);
        label = document.getElementById(labelId);
        playBtn = document.getElementById(playBtnId);
        onDateChange = callback;

        slider.addEventListener('input', () => {
            const date = dayToIso(parseInt(slider.value));
            label.textContent = formatDateLabel(date);
            if (onDateChange) onDateChange(date);
        });

        playBtn.addEventListener('click', togglePlay);
    }

    function setRange(isoStart, isoEnd) {
        startDay = isoToDays(isoStart);
        endDay = isoToDays(isoEnd);
        slider.min = startDay;
        slider.max = endDay;
        slider.value = startDay;
        label.textContent = formatDateLabel(isoStart);

        // Determine step size based on range
        const range = endDay - startDay;
        if (range > 36500) slider.step = 365;       // > 100 years: step by year
        else if (range > 3650) slider.step = 30;     // > 10 years: step by month
        else slider.step = 1;                         // otherwise: step by day
    }

    function togglePlay() {
        playing = !playing;
        playBtn.textContent = playing ? '\u275A\u275A' : '\u25B6';
        if (playing) {
            const stepMs = computePlaySpeed();
            playInterval = setInterval(() => {
                let val = parseInt(slider.value) + parseInt(slider.step);
                if (val > endDay) {
                    val = startDay;
                }
                slider.value = val;
                const date = dayToIso(val);
                label.textContent = formatDateLabel(date);
                if (onDateChange) onDateChange(date);
            }, stepMs);
        } else {
            clearInterval(playInterval);
            playInterval = null;
        }
    }

    function stop() {
        if (playing) {
            playing = false;
            playBtn.textContent = '\u25B6';
            clearInterval(playInterval);
            playInterval = null;
        }
    }

    function computePlaySpeed() {
        const range = endDay - startDay;
        const steps = range / parseInt(slider.step);
        // Aim for ~30 seconds of playback
        return Math.max(50, Math.min(500, 30000 / steps));
    }

    // Date utilities using a simple year*365 + month*30 + day approximation
    // Good enough for slider positioning; not for astronomical precision
    function isoToDays(iso) {
        const match = iso.match(/^(-?\d+)-(\d{2})-(\d{2})$/);
        if (!match) {
            // Try year-only
            const y = parseInt(iso);
            return y * 365;
        }
        const year = parseInt(match[1]);
        const month = parseInt(match[2]);
        const day = parseInt(match[3]);
        return year * 365 + (month - 1) * 30 + day;
    }

    function dayToIso(totalDays) {
        let year = Math.floor(totalDays / 365);
        let rem = totalDays - year * 365;
        if (rem < 0) { year--; rem += 365; }
        let month = Math.floor(rem / 30) + 1;
        let day = rem - (month - 1) * 30;
        if (month > 12) { month = 12; day = 31; }
        if (day < 1) day = 1;
        if (day > 31) day = 31;

        const yearStr = year < 0
            ? '-' + String(-year).padStart(4, '0')
            : String(year).padStart(4, '0');
        return `${yearStr}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    }

    function formatDateLabel(iso) {
        const match = iso.match(/^(-?\d+)-(\d{2})-(\d{2})$/);
        if (!match) return iso;
        const year = parseInt(match[1]);
        const month = parseInt(match[2]);

        const months = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                        'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

        if (year < 0) {
            return `${months[month]} ${-year} BC`;
        }
        return `${months[month]} ${year}`;
    }

    return { init, setRange, stop };
})();
