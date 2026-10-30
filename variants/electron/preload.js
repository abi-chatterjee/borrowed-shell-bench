'use strict';
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('benchBridge', {
  list: () => ipcRenderer.invoke('list'),
  save: (note) => ipcRenderer.invoke('save', note),
  remove: (id) => ipcRenderer.invoke('remove', id),
  ready: () => ipcRenderer.invoke('ready'),
});
