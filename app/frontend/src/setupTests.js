import '@testing-library/jest-dom';

const storage = {};

const storageApi = {
  getItem(key) {
    return Object.prototype.hasOwnProperty.call(storage, key) ? storage[key] : null;
  },
  setItem(key, value) {
    storage[key] = String(value);
  },
  removeItem(key) {
    delete storage[key];
  },
  clear() {
    Object.keys(storage).forEach((key) => delete storage[key]);
  },
};

Object.defineProperty(window, 'localStorage', {
  value: storageApi,
  configurable: true,
});

Object.defineProperty(globalThis, 'localStorage', {
  value: storageApi,
  configurable: true,
});
