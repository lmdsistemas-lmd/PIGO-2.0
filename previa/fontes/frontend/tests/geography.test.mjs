import test from 'node:test';
import assert from 'node:assert/strict';
import { locateCity } from '../src/utils/geography.js';

const cities = [{ibge:'1721000',nome:'Palmas',uf:'TO',lat:-10.18,lng:-48.33}, {ibge:'4117602',nome:'Palmas',uf:'PR',lat:-26.48,lng:-51.98}, {ibge:'3550308',nome:'São Paulo',uf:'SP',lat:-23.55,lng:-46.63}];
test('same city name never selects an arbitrary municipality', () => {
  assert.equal(locateCity({cidade:'Palmas'},cities),null);
  assert.equal(locateCity({cidade:'Palmas',uf:'TO'},cities).codigo_ibge,'1721000');
  assert.equal(locateCity({cidade:'Palmas',codigo_ibge:'4117602'},cities).uf,'PR');
});
test('accent-insensitive unique names work; unknown codes remain unlocated', () => {
  assert.equal(locateCity({cidade:'sao paulo'},cities).uf,'SP');
  assert.equal(locateCity({cidade:'São Paulo',codigo_ibge:'0000000'},cities),null);
  assert.equal(locateCity({cidade:'Cidade inexistente'},cities),null);
});
