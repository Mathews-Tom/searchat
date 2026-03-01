/** Alpine.js dataset store — manages active index vs snapshot mode. */

export const datasetStore = {
  snapshotName: "",
  isSnapshot: false,
  bannerVisible: false,

  init() {
    const saved = sessionStorage.getItem("activeDataset");
    if (saved) {
      const parsed = JSON.parse(saved);
      this.snapshotName = parsed.snapshotName || "";
      this.isSnapshot = parsed.isSnapshot || false;
      this.bannerVisible = this.isSnapshot;
    }
  },

  setSnapshot(name: string) {
    this.snapshotName = name;
    this.isSnapshot = !!name;
    this.bannerVisible = this.isSnapshot;
    this._save();
  },

  clearSnapshot() {
    this.snapshotName = "";
    this.isSnapshot = false;
    this.bannerVisible = false;
    this._save();
  },

  _save() {
    sessionStorage.setItem(
      "activeDataset",
      JSON.stringify({
        snapshotName: this.snapshotName,
        isSnapshot: this.isSnapshot,
      }),
    );
  },
};
