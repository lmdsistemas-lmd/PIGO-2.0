import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizePreferences,preferenceKey } from '../src/utils/dashboardPreferences.js';
test('saved layout handles new and removed widgets without duplicates or invalid chart types',()=>{
 const blocks=[{id:'a'},{id:'b'},{id:'new'}];
 assert.deepEqual(normalizePreferences({order:['b','b','removed'],hidden:['a','removed'],types:{a:'donut',b:'script',removed:'bar'}},blocks),{order:['b','a','new'],hidden:['a'],types:{a:'donut'}});
});
test('preferences are isolated by user, company, tenant and dashboard',()=>{
 const user={tenant_id:'t',id:'u'};const initial=preferenceKey('vendas',user,1);
 for(const key of [preferenceKey('vendas',{...user,id:'v'},1),preferenceKey('vendas',user,2),preferenceKey('vendas',{...user,tenant_id:'z'},1),preferenceKey('financeiro',user,1)])assert.notEqual(key,initial);
});
