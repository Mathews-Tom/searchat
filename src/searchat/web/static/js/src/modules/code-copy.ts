/** Code copy utility — adds clipboard copy buttons to code blocks. */

export function initCodeCopy(): void {
  document.querySelectorAll<HTMLElement>("pre code").forEach((block) => {
    // Skip if already has a copy button or explicitly opted out
    if (block.parentElement?.querySelector(".code-copy-btn")) return;
    if (block.parentElement?.hasAttribute("data-no-copy")) return;

    const btn = document.createElement("button");
    btn.className = "code-copy-btn";
    btn.textContent = "Copy";
    btn.setAttribute("type", "button");

    btn.addEventListener("click", () => {
      const text = block.textContent || "";
      navigator.clipboard.writeText(text).then(
        () => {
          btn.textContent = "Copied!";
          setTimeout(() => {
            btn.textContent = "Copy";
          }, 2000);
        },
        () => {
          btn.textContent = "Failed";
          setTimeout(() => {
            btn.textContent = "Copy";
          }, 2000);
        },
      );
    });

    block.parentElement?.style.setProperty("position", "relative");
    block.parentElement?.appendChild(btn);
  });
}
