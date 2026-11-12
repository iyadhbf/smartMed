(function () {
  "use strict";

  /* Mobile navigation -------------------------------------------------- */
  const navToggle = document.querySelector("[data-nav-toggle]");
  const mobileNav = document.getElementById("mobile-navigation");

  if (navToggle && mobileNav) {
    const icon = navToggle.querySelector("i");

    const setOpen = (open) => {
      mobileNav.hidden = !open;
      navToggle.setAttribute("aria-expanded", String(open));
      navToggle.setAttribute("aria-label", open ? "Fermer le menu" : "Ouvrir le menu");
      if (icon) {
        icon.classList.toggle("bi-list", !open);
        icon.classList.toggle("bi-x-lg", open);
      }
    };

    navToggle.addEventListener("click", () => setOpen(mobileNav.hidden));

    mobileNav.querySelectorAll("a").forEach((link) => {
      link.addEventListener("click", () => setOpen(false));
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !mobileNav.hidden) {
        setOpen(false);
        navToggle.focus();
      }
    });
  }

  /* Account menu ------------------------------------------------------- */
  document.querySelectorAll("details.sm-user").forEach((menu) => {
    const summary = menu.querySelector("summary");

    document.addEventListener("click", (event) => {
      if (menu.open && !menu.contains(event.target)) {
        menu.open = false;
      }
    });

    menu.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && menu.open) {
        menu.open = false;
        if (summary) summary.focus();
      }
    });
  });

  /* Services carousel -------------------------------------------------- */
  document.querySelectorAll("[data-carousel]").forEach((rail) => {
    if (!rail.id) return;

    const prev = document.querySelector('[data-carousel-prev="#' + rail.id + '"]');
    const next = document.querySelector('[data-carousel-next="#' + rail.id + '"]');
    const gap = 20;

    const step = () => {
      const card = rail.querySelector(".service-card");
      return card ? card.getBoundingClientRect().width + gap : rail.clientWidth * 0.8;
    };

    const update = () => {
      const maxScroll = rail.scrollWidth - rail.clientWidth - 2;
      if (prev) prev.disabled = rail.scrollLeft <= 2;
      if (next) next.disabled = rail.scrollLeft >= maxScroll;
    };

    if (prev) {
      prev.addEventListener("click", () => {
        rail.scrollBy({ left: -step(), behavior: "smooth" });
      });
    }

    if (next) {
      next.addEventListener("click", () => {
        rail.scrollBy({ left: step(), behavior: "smooth" });
      });
    }

    rail.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    update();
  });

  /* Booking bars (home page + booking page chooser) --------------------- */
  document.querySelectorAll("[data-booking-form]").forEach(initBookingForm);

  function initBookingForm(form) {
  const specialtySelect = form.querySelector("#booking-specialty");
  const doctorSelect = form.querySelector("#booking-doctor");
  const dateInput = form.querySelector("#booking-date");
  const statusEl = form.querySelector("[data-booking-status]");
  const submitBtn = form.querySelector("[data-booking-submit]");
  const doctorsUrl = form.dataset.doctorsUrl;

  if (!specialtySelect || !doctorSelect || !statusEl || !submitBtn || !doctorsUrl) return;

  let pendingDoctorId = null;
  let requestToken = 0;

  const setStatus = (message) => {
    statusEl.textContent = message || "";
  };

  const setDoctorPlaceholder = (label) => {
    doctorSelect.replaceChildren(new Option(label, ""));
    doctorSelect.disabled = true;
    doctorSelect.required = false;
    submitBtn.disabled = false;
  };

  const applyDoctors = (doctors) => {
    const desired = pendingDoctorId || doctorSelect.value;
    const placeholder = doctors.length ? "Choisir un médecin" : "Aucun médecin disponible";

    doctorSelect.replaceChildren(new Option(placeholder, ""));
    doctors.forEach((doctor) => {
      doctorSelect.add(new Option(doctor.name, String(doctor.id)));
    });

    doctorSelect.disabled = doctors.length === 0;
    doctorSelect.required = doctors.length > 0;
    submitBtn.disabled = doctors.length === 0;

    if (desired && doctors.some((doctor) => String(doctor.id) === String(desired))) {
      doctorSelect.value = String(desired);
    }

    pendingDoctorId = null;
    setStatus(doctors.length ? "" : "Aucun médecin n'est disponible pour cette spécialité.");
  };

  const loadDoctors = async () => {
    const specialtyId = specialtySelect.value;

    if (!specialtyId) {
      setDoctorPlaceholder("Choisir une spécialité d'abord");
      setStatus("");
      return;
    }

    const token = ++requestToken;
    doctorSelect.disabled = true;
    doctorSelect.required = false;
    doctorSelect.replaceChildren(new Option("Chargement…", ""));
    submitBtn.disabled = true;
    setStatus("");

    try {
      const response = await fetch(doctorsUrl + "?specialty=" + encodeURIComponent(specialtyId), {
        headers: { Accept: "application/json" },
      });
      if (!response.ok) throw new Error("HTTP " + response.status);

      const payload = await response.json();
      if (token !== requestToken) return;

      applyDoctors(Array.isArray(payload.doctors) ? payload.doctors : []);
    } catch (error) {
      if (token !== requestToken) return;
      setDoctorPlaceholder("Indisponible");
      submitBtn.disabled = true;
      setStatus("Impossible de charger les médecins. Veuillez réessayer.");
    }
  };

  specialtySelect.addEventListener("change", loadDoctors);

  document.querySelectorAll("[data-book-doctor]").forEach((button) => {
    button.addEventListener("click", () => {
      const specialtyId = button.dataset.bookSpecialty;
      const doctorId = button.dataset.bookDoctor;
      if (!specialtyId || !doctorId) return;

      pendingDoctorId = doctorId;

      if (specialtySelect.value !== specialtyId) {
        specialtySelect.value = specialtyId;
        loadDoctors();
      } else if (doctorSelect.querySelector('option[value="' + doctorId + '"]')) {
        doctorSelect.value = doctorId;
        pendingDoctorId = null;
        setStatus("");
      } else {
        loadDoctors();
      }

      const hero = document.getElementById("accueil");
      if (hero) {
        hero.scrollIntoView({ behavior: "smooth", block: "start" });
      }
      window.setTimeout(() => {
        if (dateInput) dateInput.focus({ preventScroll: true });
      }, 650);
    });
  });

  form.addEventListener("submit", (event) => {
    if (specialtySelect.value && doctorSelect.disabled) {
      event.preventDefault();
      setStatus("Veuillez choisir un médecin disponible.");
    }
  });

  if (specialtySelect.value) {
    loadDoctors();
  }
  }

  /* Confirmable POST forms ---------------------------------------------- */
  document.querySelectorAll("form[data-confirm-submit]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!window.confirm(form.dataset.confirmSubmit)) {
        event.preventDefault();
      }
    });
  });
})();
