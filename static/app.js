const methods = document.querySelector("[data-methods]");
const addMethod = document.querySelector("[data-add-method]");

if (methods && addMethod) {
  const template = document.querySelector("#method-template");
  const maximum = Number(methods.dataset.max);
  const updateAddButton = () => {
    addMethod.disabled = methods.childElementCount >= maximum;
  };
  addMethod.addEventListener("click", () => {
    if (methods.childElementCount >= maximum) return;
    methods.append(template.content.cloneNode(true));
    methods.lastElementChild.querySelector("input").focus();
    updateAddButton();
  });
  methods.addEventListener("click", (event) => {
    const button = event.target.closest("[data-remove]");
    if (!button) return;
    button.closest(".method-row").remove();
    updateAddButton();
    addMethod.focus();
  });
  updateAddButton();
}

for (const form of document.querySelectorAll("[data-confirm]")) {
  form.addEventListener("submit", (event) => {
    if (!window.confirm(form.dataset.confirm)) event.preventDefault();
  });
}
