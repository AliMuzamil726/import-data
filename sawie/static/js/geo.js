/* Geometry helpers shared by the field editor and the map dashboard. */
window.SAWIE_GEO = (function () {
  const EARTH_RADIUS_M = 6378137;
  const SQ_M_PER_ACRE = 4046.8564224;

  function toRad(value) {
    return (value * Math.PI) / 180;
  }

  /* Spherical excess area of a GeoJSON ring, in square metres. */
  function ringArea(coords) {
    if (!coords || coords.length < 3) return 0;
    let total = 0;
    for (let i = 0; i < coords.length; i += 1) {
      const [lng1, lat1] = coords[i];
      const [lng2, lat2] = coords[(i + 1) % coords.length];
      total += toRad(lng2 - lng1) * (2 + Math.sin(toRad(lat1)) + Math.sin(toRad(lat2)));
    }
    return Math.abs((total * EARTH_RADIUS_M * EARTH_RADIUS_M) / 2);
  }

  function areaInAcres(geometry) {
    if (!geometry || geometry.type !== 'Polygon') return 0;
    const [outer, ...holes] = geometry.coordinates;
    const net = ringArea(outer) - holes.reduce((sum, ring) => sum + ringArea(ring), 0);
    return net / SQ_M_PER_ACRE;
  }

  const polygonStyle = { color: '#5C8A34', weight: 2, fillColor: '#9DC46A', fillOpacity: 0.30 };

  function healthStyle(colour) {
    return { color: colour, weight: 2, fillColor: colour, fillOpacity: 0.28 };
  }

  /* Tile providers. OpenStreetMap (Street) is the DEFAULT because it always
     loads, even over slow links or Cloudflare tunnels. Satellite (Esri) and a
     labelled hybrid are optional layers the user can switch to. */
  function streetLayer() {
    return L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19, attribution: '&copy; OpenStreetMap contributors',
    });
  }

  function satelliteLayer() {
    return L.tileLayer(
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      { maxZoom: 19, attribution: 'Imagery &copy; Esri' }
    );
  }

  /* Thin place-name/road labels drawn over satellite imagery. */
  function labelsLayer() {
    return L.tileLayer(
      'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
      { maxZoom: 19, attribution: '', pane: 'overlayPane' }
    );
  }

  /* Ordered so the FIRST entry is what Leaflet shows by default when passed
     as the initial layer. Street first = reliable first paint. */
  function baseLayers() {
    return {
      Street: streetLayer(),
      Satellite: satelliteLayer(),
    };
  }

  return {
    areaInAcres, ringArea, polygonStyle, healthStyle,
    baseLayers, streetLayer, satelliteLayer, labelsLayer,
  };
})();
