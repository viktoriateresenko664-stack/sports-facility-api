let map = null;
let markers = [];

export function initMap(facilities) {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => _initMap(facilities));
    } else {
        _initMap(facilities);
    }
}

function _initMap(facilities) {
    const mapContainer = document.getElementById('map');
    if (!mapContainer) return;

    if (typeof L === 'undefined') {
        return;
    }

    createMap(facilities);
}

function createMap(facilities) {
    const mapContainer = document.getElementById('map');
    if (!mapContainer) return;

    const center = [55.7558, 37.6176];
    map = L.map('map').setView(center, 11);

    L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        subdomains: 'abcd',
        maxZoom: 19,
        minZoom: 10
    }).addTo(map);

    map.attributionControl.setPrefix('');

    addMarkers(facilities);
}

function buildFacilityPopupElement(facility) {
    const container = document.createElement('div');

    const title = document.createElement('strong');
    title.textContent = facility.name || 'Объект';
    container.appendChild(title);
    container.appendChild(document.createElement('br'));

    container.appendChild(document.createTextNode(facility.address || ''));
    container.appendChild(document.createElement('br'));

    container.appendChild(document.createTextNode(facility.hours || '09:00 - 18:00'));
    container.appendChild(document.createElement('br'));

    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = 'Подробнее';
    button.style.marginTop = '8px';
    button.style.padding = '4px 12px';
    button.style.background = '#0d2b4e';
    button.style.color = 'white';
    button.style.border = 'none';
    button.style.borderRadius = '4px';
    button.style.cursor = 'pointer';
    button.addEventListener('click', () => {
        const facilityId = Number(facility.id);
        if (!Number.isInteger(facilityId) || facilityId <= 0) return;

        const params = new URLSearchParams({
            id: String(facilityId),
            name: String(facility.name || ''),
            address: String(facility.address || ''),
            image: String(facility.image_url || ''),
        });
        window.location.href = `facility.html?${params.toString()}`;
    });

    container.appendChild(button);
    return container;
}

async function addMarkers(facilities) {
    if (!map) return;

    markers.forEach(marker => map.removeLayer(marker));
    markers = [];

    for (const facility of facilities) {
        const coords = getCoordinatesFromFacility(facility);

        if (!coords) {
            continue;
        }

        const marker = L.marker(coords).addTo(map);
        marker.bindPopup(buildFacilityPopupElement(facility));

        marker.on('click', () => {
            localStorage.setItem('selectedFacilityId', String(facility.id));
            localStorage.setItem('selectedFacilityName', facility.name);
            localStorage.setItem('selectedFacilityAddress', facility.address);
            highlightFacilityInList(facility.id);
        });

        markers.push(marker);
    }

    const firstWithCoords = facilities.find(f => getCoordinatesFromFacility(f));
    if (firstWithCoords) {
        const [lat, lng] = getCoordinatesFromFacility(firstWithCoords);
        map.setView([lat, lng], 12);
    }
}

function getCoordinatesFromFacility(facility) {
    const lat = Number(facility.latitude);
    const lng = Number(facility.longitude);
    if (Number.isFinite(lat) && Number.isFinite(lng)) {
        return [lat, lng];
    }
    return null;
}

function highlightFacilityInList(facilityId) {
    document.querySelectorAll('.facility-item').forEach(item => {
        item.classList.remove('selected');
    });

    const selectedItem = document.querySelector(`.facility-item[data-id="${facilityId}"]`);
    if (selectedItem) {
        selectedItem.classList.add('selected');
        selectedItem.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
}

export function updateMapMarkers(facilities) {
    if (!map) {
        initMap(facilities);
    } else {
        addMarkers(facilities);
    }
}
