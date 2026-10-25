// Runs before React. Browsers with storage blocked ("block all cookies", some in-app webviews) throw on ANY access to
// localStorage/sessionStorage; with 200+ call sites the whole app fell into the error screen. Replace only a storage
// that throws on read with an in-memory one. A merely full storage (setItem throws) is left alone so saved data stays readable.
export const STORAGE_SHIM_SCRIPT = `(function(){
function mem(){var d={};return{
  getItem:function(k){return Object.prototype.hasOwnProperty.call(d,k)?d[k]:null},
  setItem:function(k,v){d[k]=String(v)},
  removeItem:function(k){delete d[k]},
  clear:function(){d={}},
  key:function(i){var ks=Object.keys(d);return i<ks.length?ks[i]:null},
  get length(){return Object.keys(d).length}}}
["localStorage","sessionStorage"].forEach(function(n){
  var blocked=false;
  try{window[n].getItem("__aoep_probe__")}catch(e){blocked=true}
  if(blocked){try{Object.defineProperty(window,n,{value:mem(),configurable:true,writable:true})}catch(e){}}
});
})();`;
