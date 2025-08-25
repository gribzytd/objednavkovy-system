// script.js

// --- Globálne premenné a nastavenia ---
const API_URL = 'https://objednavkovy-system-1.onrender.com';

// Premenné na sledovanie aktuálne zobrazeného mesiaca a roka
let aktualnyDatum = new Date();
let vsetkyObjednavky = []; // Miesto na uloženie všetkých objednávok

// Výber elementov z HTML, s ktorými budeme pracovať
const kalendarGrid = document.getElementById('kalendar-grid');
const nazovMesiacaEl = document.getElementById('nazov-mesiaca');
const predchadzajuciMesiacBtn = document.getElementById('predchadzajuci-mesiac');
const nasledujuciMesiacBtn = document.getElementById('nasledujuci-mesiac');
const formular = document.getElementById('formular');
const spravaDiv = document.getElementById('sprava');

// --- Funkcie ---

/**
 * Hlavná funkcia na vykreslenie kalendára pre daný rok a mesiac.
 */
function vykresliKalendar() {
    const rok = aktualnyDatum.getFullYear();
    const mesiac = aktualnyDatum.getMonth(); // 0 = Január, 11 = December

    // Názvy mesiacov pre hlavičku kalendára
    const nazvyMesiacov = ["Január", "Február", "Marec", "Apríl", "Máj", "Jún", "Júl", "August", "September", "Október", "November", "December"];
    nazovMesiacaEl.textContent = `${nazvyMesiacov[mesiac]} ${rok}`;

    // Vyčistíme starý kalendár
    kalendarGrid.innerHTML = '';

    // Zistíme, koľko dní má mesiac a ktorý deň v týždni je prvý
    const prvyDenMesiaca = new Date(rok, mesiac, 1).getDay(); // 0=Nedeľa, 1=Pondelok...
    const pocetDniVMesiaci = new Date(rok, mesiac + 1, 0).getDate();
    
    // Korekcia pre Slovensko, kde týždeň začína pondelkom (0=Po, 6=Ne)
    const posunPrvehoDna = (prvyDenMesiaca === 0) ? 6 : prvyDenMesiaca - 1;

    // Vytvoríme prázdne políčka pre dni pred začiatkom mesiaca
    for (let i = 0; i < posunPrvehoDna; i++) {
        const denDiv = document.createElement('div');
        denDiv.classList.add('kalendar-den', 'prazdny');
        kalendarGrid.appendChild(denDiv);
    }

    // Vytvoríme políčka pre každý deň v mesiaci
    for (let i = 1; i <= pocetDniVMesiaci; i++) {
        const denDiv = document.createElement('div');
        denDiv.classList.add('kalendar-den');
        denDiv.textContent = i;
        
        const datumString = `${rok}-${String(mesiac + 1).padStart(2, '0')}-${String(i).padStart(2, '0')}`;
        
        // Zvýrazníme dnešný deň
        const dnes = new Date();
        if (i === dnes.getDate() && mesiac === dnes.getMonth() && rok === dnes.getFullYear()) {
            denDiv.classList.add('dnes');
        }
        
        // Spracujeme objednávky pre tento deň
        const objednavkyNaDen = vsetkyObjednavky.filter(o => o.datum === datumString);
        const pocetObsadenych = objednavkyNaDen.length;

        // Vytvoríme tooltip
        const tooltip = document.createElement('span');
        tooltip.classList.add('tooltip');
        let tooltipText = 'Voľné časy:<br>';
        const vsetkyCasy = ["08:00", "09:00", "10:00", "16:00", "17:00"];
        const obsadeneCasy = objednavkyNaDen.map(o => o.cas);
        
        vsetkyCasy.forEach(cas => {
            if (obsadeneCasy.includes(cas)) {
                tooltipText += `<span style="text-decoration: line-through;">${cas}</span><br>`;
            } else {
                tooltipText += `${cas}<br>`;
            }
        });
        tooltip.innerHTML = tooltipText;
        denDiv.appendChild(tooltip);

        // Nastavíme farbu dňa podľa obsadenosti
        if (pocetObsadenych === 0) {
            denDiv.classList.add('volny');
        } else if (pocetObsadenych >= vsetkyCasy.length) {
            denDiv.classList.add('plny');
        } else {
            denDiv.classList.add('ciastocne');
        }

        // Pridáme event listener pre kliknutie (ak deň nie je plný)
        if (!denDiv.classList.contains('plny')) {
            denDiv.addEventListener('click', () => {
                document.getElementById('datum').value = datumString;
                // Plynulé posunutie na formulár
                document.getElementById('objednavkovy-formular').scrollIntoView({ behavior: 'smooth' });
            });
        }
        
        kalendarGrid.appendChild(denDiv);
    }
}

/**
 * Načíta všetky objednávky zo servera a potom vykreslí kalendár.
 */
async function nacitajDataAVykresli() {
    try {
        const response = await fetch(`${API_URL}/api/terminy`);
        vsetkyObjednavky = await response.json();
        vykresliKalendar();
    } catch (error) {
        console.error('Chyba pri načítavaní dát:', error);
        kalendarGrid.innerHTML = '<p>Nepodarilo sa načítať dáta zo servera.</p>';
    }
}

/**
 * Odošle dáta z formulára na server a vytvorí novú objednávku.
 */
formular.addEventListener('submit', async function(event) {
    event.preventDefault();
    
    const data = {
        meno: document.getElementById('meno').value,
        datum: document.getElementById('datum').value,
        cas: document.getElementById('cas').value
    };
    
    spravaDiv.textContent = 'Odosielam...';

    try {
        const response = await fetch(`${API_URL}/api/objednat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        
        const vysledok = await response.json();
        
        if (response.ok && vysledok.status === 'success') {
            spravaDiv.textContent = 'Ďakujeme! Vaša objednávka bola prijatá.';
            spravaDiv.style.color = 'green';
            formular.reset();
            // Znova načítame dáta a prekreslíme kalendár, aby sa zobrazila zmena
            nacitajDataAVykresli();
        } else {
            spravaDiv.textContent = `Chyba: ${vysledok.message || 'Neznáma chyba'}`;
            spravaDiv.style.color = 'red';
        }
    } catch (error) {
        spravaDiv.textContent = 'Nastala chyba pri komunikácii so serverom.';
        spravaDiv.style.color = 'red';
    }
});

// Event listenery pre prepínanie mesiacov
predchadzajuciMesiacBtn.addEventListener('click', () => {
    aktualnyDatum.setMonth(aktualnyDatum.getMonth() - 1);
    vykresliKalendar();
});

nasledujuciMesiacBtn.addEventListener('click', () => {
    aktualnyDatum.setMonth(aktualnyDatum.getMonth() + 1);
    vykresliKalendar();
});

// --- Prvotné spustenie ---
// Keď sa stránka načíta, hneď načítame všetky dáta a vykreslíme kalendár.
document.addEventListener('DOMContentLoaded', nacitajDataAVykresli);