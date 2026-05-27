(function () {
  "use strict";

  const DESTINATIONS = [
    {
      id: "crete-chania",
      latitude: 35.5138,
      longitude: 24.0180,
      country: "Greece",
      countryId: "GR",
      title: "Crete in Six Days",
      url: "pages/chania-crete.html"
    },
    {
      id: "greece-second-trip",
      latitude: 35.5138,
      longitude: 24.0180,
      country: "Greece",
      countryId: "GR",
      title: "3 Days in Olympus",
      url: "pages/olympus-3days.html"
    },
    {
      id: "maldives",
      latitude: 3.2028,
      longitude: 73.2207,
      country: "Maldives",
      countryId: "MV",
      title: "Paradise Islands",
      url: "pages/salty-life.html"
    },
    {
      id: "france",
      latitude: 46.2276,
      longitude: 2.2137,
      country: "France",
      countryId: "FR",
      title: "Val Thorens in 5 Days",
      url: "pages/val-thorens-5days.html"
    },
    {
      id: "portugal",
      latitude: 39.3999,
      longitude: -8.2245,
      country: "Portugal",
      countryId: "PT",
      title: "Coastal Wonders",
      url: "pages/salty-life.html"
    }
  ];

  const containerId = "globeContainer";
  const popup = document.getElementById("globePopup");
  const popupCountry = document.getElementById("globePopupCountry");
  const popupTrips = document.getElementById("globePopupTrips");
  const popupClose = document.getElementById("globePopupClose");

  if (!document.getElementById(containerId)) return;

  function groupTripsByCountry(items) {
    const grouped = new Map();

    items.forEach((item) => {
      const key = item.countryId;

      if (!grouped.has(key)) {
        grouped.set(key, {
          id: item.id,
          latitude: item.latitude,
          longitude: item.longitude,
          country: item.country,
          countryId: item.countryId,
          trips: []
        });
      }

      grouped.get(key).trips.push({
        id: item.id,
        title: item.title,
        url: item.url
      });
    });

    return Array.from(grouped.values());
  }

  const markerData = groupTripsByCountry(DESTINATIONS);

  const root = am5.Root.new(containerId);

  root.setThemes([
    am5themes_Animated.new(root)
  ]);

  const chart = root.container.children.push(
    am5map.MapChart.new(root, {
      projection: am5map.geoOrthographic(),
      panX: "rotateX",
      panY: "rotateY",
      wheelX: "none",
      wheelY: "none",
      pinchZoom: false,
      paddingTop: 0,
      paddingBottom: 0,
      paddingLeft: 0,
      paddingRight: 0
    })
  );

  chart.set("background", am5.Rectangle.new(root, {
    fill: am5.color(0x000000),
    fillOpacity: 0
  }));

  const backgroundSeries = chart.series.push(
    am5map.MapPolygonSeries.new(root, {})
  );

  backgroundSeries.mapPolygons.template.setAll({
    fill: am5.color(0xe9eef3),
    fillOpacity: 1,
    strokeOpacity: 0
  });

  backgroundSeries.data.push({
    geometry: am5map.getGeoRectangle(90, 180, -90, -180)
  });

  const highlightedCountryIds = [...new Set(DESTINATIONS.map((item) => item.countryId))];

  const polygonSeries = chart.series.push(
    am5map.MapPolygonSeries.new(root, {
      geoJSON: am5geodata_worldLow,
      exclude: ["AQ"]
    })
  );

  polygonSeries.mapPolygons.template.setAll({
    fill: am5.color(0x6d97d1),
    stroke: am5.color(0xd9e2ef),
    strokeWidth: 0.6,
    interactive: false
  });

  polygonSeries.mapPolygons.template.adapters.add("fill", function (fill, target) {
    const dataItem = target.dataItem;
    if (!dataItem) return fill;

    const context = dataItem.dataContext;
    if (!context) return fill;

    if (highlightedCountryIds.includes(context.id)) {
      return am5.color(0xf2c94c);
    }

    return fill;
  });

  const graticuleSeries = chart.series.push(
    am5map.GraticuleSeries.new(root, {})
  );

  graticuleSeries.mapLines.template.setAll({
    stroke: am5.color(0xbfc6cf),
    strokeOpacity: 0.7,
    strokeWidth: 1
  });

  const pointSeries = chart.series.push(
    am5map.MapPointSeries.new(root, {})
  );

  pointSeries.bullets.push(function (root, series, dataItem) {
    const markerWrap = am5.Container.new(root, {
      width: 42,
      height: 52,
      centerX: am5.p50,
      centerY: am5.p100,
      cursorOverStyle: "pointer",
      interactive: true
    });

    const pulse = markerWrap.children.push(
      am5.Circle.new(root, {
        x: 21,
        y: 52,
        radius: 5,
        fill: am5.color(0xff5a1f),
        fillOpacity: 0.22
      })
    );

    pulse.animate({
      key: "scale",
      from: 0.8,
      to: 2,
      duration: 1800,
      easing: am5.ease.out(am5.ease.cubic),
      loops: Infinity
    });

    pulse.animate({
      key: "opacity",
      from: 0.65,
      to: 0,
      duration: 1800,
      easing: am5.ease.out(am5.ease.cubic),
      loops: Infinity
    });

    markerWrap.children.push(
      am5.Ellipse.new(root, {
        x: 21,
        y: 50,
        width: 14,
        height: 6,
        fill: am5.color(0x000000),
        fillOpacity: 0.14
      })
    );

    markerWrap.children.push(
      am5.Graphics.new(root, {
        x: 21,
        y: 30,
        svgPath: "M0,-16 C8,-16 14,-10 14,-2 C14,8 0,22 0,22 C0,22 -14,8 -14,-2 C-14,-10 -8,-16 0,-16 Z",
        fill: am5.color(0xff5a1f),
        stroke: am5.color(0xff7a3d),
        strokeWidth: 1.5,
        centerX: am5.p50,
        centerY: am5.p50
      })
    );

    markerWrap.children.push(
      am5.Circle.new(root, {
        x: 21,
        y: 27,
        radius: 5.8,
        fill: am5.color(0xff7a1a),
        stroke: am5.color(0xffa366),
        strokeWidth: 1
      })
    );

    markerWrap.children.push(
      am5.Circle.new(root, {
        x: 17,
        y: 23,
        radius: 2.8,
        fill: am5.color(0xffffff),
        fillOpacity: 0.22
      })
    );

    markerWrap.children.push(
      am5.Circle.new(root, {
        x: 21,
        y: 30,
        radius: 18,
        fill: am5.color(0xffffff),
        fillOpacity: 0
      })
    );

    markerWrap.events.on("pointerover", function () {
      markerWrap.animate({ key: "scale", to: 1.08, duration: 180 });
    });

    markerWrap.events.on("pointerout", function () {
      markerWrap.animate({ key: "scale", to: 1, duration: 180 });
    });

    markerWrap.events.on("click", function (ev) {
      const data = dataItem.dataContext;
      showPopup(data, ev.originalEvent);
    });

    return am5.Bullet.new(root, {
      sprite: markerWrap
    });
  });

  pointSeries.data.setAll(markerData);

  let autoRotate = true;
  let currentAnimation = null;

  function rotateGlobe() {
    if (!autoRotate) return;

    const currentRotation = chart.get("rotationX") || 0;

    currentAnimation = chart.animate({
      key: "rotationX",
      from: currentRotation,
      to: currentRotation + 360,
      duration: 30000,
      loops: 1
    });

    currentAnimation.events.on("stopped", function () {
      if (autoRotate) rotateGlobe();
    });
  }

  function stopAutoRotate() {
    autoRotate = false;
    if (currentAnimation) {
      currentAnimation.stop();
      currentAnimation = null;
    }
  }

  rotateGlobe();

  chart.chartContainer.events.on("pointerdown", function () {
    stopAutoRotate();
    closePopup();
  });

  function renderTrips(trips) {
    if (!popupTrips) return;

    popupTrips.innerHTML = "";

    trips.forEach(function (trip) {
      const tripBlock = document.createElement("div");
      tripBlock.className = "globe-popup-trip";

      const title = document.createElement("h3");
      title.className = "globe-popup-title";
      title.textContent = trip.title;

      const button = document.createElement("a");
      button.className = "globe-popup-btn";
      button.href = trip.url;
      button.textContent = "Learn More";

      tripBlock.appendChild(title);
      tripBlock.appendChild(button);

      popupTrips.appendChild(tripBlock);
    });
  }

  function showPopup(data, originalEvent) {
    if (!popup) return;

    popupCountry.textContent = data.country;
    renderTrips(data.trips);

    popup.style.left = originalEvent.clientX + "px";
    popup.style.top = originalEvent.clientY + "px";

    popup.classList.add("open");
    popup.setAttribute("aria-hidden", "false");
  }

  function closePopup() {
    if (!popup) return;
    popup.classList.remove("open");
    popup.setAttribute("aria-hidden", "true");
  }

  if (popupClose) {
    popupClose.addEventListener("click", closePopup);
  }

  document.addEventListener("click", function (e) {
    const clickedInsidePopup = popup && popup.contains(e.target);
    const clickedInsideMap = e.target.closest("#" + containerId);

    if (!clickedInsidePopup && !clickedInsideMap) {
      closePopup();
    }
  });

  chart.appear(1000, 100);
})();