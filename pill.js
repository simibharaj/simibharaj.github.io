/* lacquer pills: draws a glossy 3d capsule behind every [data-pill] element inside a [data-pills] group.
   the element keeps its own real text on top, so the label is always crisp. colors: white, blush, pink, ink. */
import * as THREE from 'three';
import {RoomEnvironment} from 'three/addons/environments/RoomEnvironment.js';
const COL={white:'#f7f6f4',cream:'#fbf6ec',blush:'#ffc9dc',pink:'#ff3d8b',lemon:'#ffd54a',mint:'#5fd3a3',sky:'#6fbcff',lilac:'#b996ff',ink:'#151517',cherry:'#e0193a'};
const groups=[...document.querySelectorAll('[data-pills]')];
const still=matchMedia('(prefers-reduced-motion: reduce)').matches;
let envTex=null;
function lacquer(c){return new THREE.MeshPhysicalMaterial({color:c,roughness:.14,clearcoat:1,clearcoatRoughness:.03,sheen:.2,envMapIntensity:1.1})}
/* two-tone capsule like a lacquer pill box: a body half and a slightly larger cap half that slides over it */
function half(mat,r,len,dir){const g=new THREE.Group();
  const c=new THREE.Mesh(new THREE.CylinderGeometry(r,r,len,64,1,true),mat);c.rotation.z=Math.PI/2;c.position.x=dir*len/2;g.add(c);
  const cap=new THREE.Mesh(new THREE.SphereGeometry(r,64,32,0,Math.PI*2,0,Math.PI/2),mat);cap.rotation.z=-dir*Math.PI/2;cap.position.x=dir*len;g.add(cap);
  const rim=new THREE.Mesh(new THREE.RingGeometry(r*.86,r,64),mat);rim.rotation.y=dir*Math.PI/2;g.add(rim);return g}
function capsule(c1,c2,r,len){const g=new THREE.Group(),h=Math.max(.5,len/2);g.add(half(lacquer(c1),r*.97,h,-1));
  const cap=half(lacquer(c2),r*1.01,h,1);cap.position.x=-r*.08;g.add(cap);return g}
const sp=(k,d,x,v,t,dt)=>{v+=(-k*(x-t)-d*v)*dt;return[x+v*dt,v]};
function setup(box){
  const cv=document.createElement('canvas');cv.className='pillgl';cv.setAttribute('aria-hidden','true');box.prepend(cv);
  let r;try{r=new THREE.WebGLRenderer({canvas:cv,antialias:true,alpha:true})}catch(e){cv.remove();return}
  box.classList.add('pilled');document.documentElement.classList.add('pills-on');
  r.setPixelRatio(Math.min(2,devicePixelRatio||1));r.toneMapping=THREE.ACESFilmicToneMapping;r.toneMappingExposure=1.0;r.outputColorSpace=THREE.SRGBColorSpace;
  const scene=new THREE.Scene();scene.environment=new THREE.PMREMGenerator(r).fromScene(new RoomEnvironment(r),.04).texture;
  const cam=new THREE.OrthographicCamera(-1,1,1,-1,-2000,2000);cam.position.z=1000;
  const P=[...box.querySelectorAll('[data-pill]')].map(el=>({el,g:new THREE.Group(),key:'',hover:false,press:false,sq:0,vsq:0,rx:0,vrx:0,ry:0,vry:0,l:0,vl:0}));
  P.forEach(p=>{scene.add(p.g);
    p.el.addEventListener('pointerenter',()=>p.hover=true);p.el.addEventListener('pointerleave',()=>{p.hover=false;p.press=false});
    p.el.addEventListener('pointerdown',()=>{p.press=true;p.vsq-=5});addEventListener('pointerup',()=>{if(p.press){p.press=false;p.vsq+=6}})});
  let mx=0,my=0;addEventListener('pointermove',e=>{mx=e.clientX;my=e.clientY},{passive:true});
  let cw=0,ch=0;
  function colors(p){const cur=p.el.classList.contains('cur')&&p.el.dataset.pillCur;const v=(cur||p.el.dataset.pill||'white').split('|');return [COL[v[0]]||v[0],COL[v[1]||v[0]]||v[1]||v[0]]}
  function build(p){const b=p.el.getBoundingClientRect(),c=colors(p),key=[b.width|0,b.height|0,c].join('|');if(key===p.key)return;p.key=key;
    p.g.traverse(o=>{if(o.geometry)o.geometry.dispose()});p.g.clear();p.g.add(capsule(c[0],c[1],b.height/2,Math.max(1,b.width-b.height)))}
  function size(){const b=cv.getBoundingClientRect();cw=b.width;ch=b.height;r.setSize(cw,ch,false);cam.left=-cw/2;cam.right=cw/2;cam.top=ch/2;cam.bottom=-ch/2;cam.updateProjectionMatrix();P.forEach(p=>p.key='')}
  new ResizeObserver(size).observe(box);addEventListener('resize',size);
  new MutationObserver(()=>P.forEach(p=>p.key='')).observe(box,{subtree:true,attributes:true,attributeFilter:['class']});
  let last=performance.now(),vis=true;new IntersectionObserver(e=>vis=e[0].isIntersecting).observe(box);
  (function frame(now){requestAnimationFrame(frame);const dt=Math.min(.033,(now-last)/1000);last=now;if(!vis||!cw)return;const cb=cv.getBoundingClientRect();
    for(const p of P){build(p);const b=p.el.getBoundingClientRect(),cx=b.left+b.width/2,cy=b.top+b.height/2;
      const nx=p.hover?Math.max(-1,Math.min(1,(mx-cx)/(b.width/2))):0,ny=p.hover?Math.max(-1,Math.min(1,(my-cy)/(b.height/2))):0;
      [p.sq,p.vsq]=sp(300,12,p.sq,p.vsq,p.press?-.08:0,dt);[p.l,p.vl]=sp(120,14,p.l,p.vl,p.hover&&!still?2:0,dt);
      [p.rx,p.vrx]=sp(60,10,p.rx,p.vrx,still?0:ny*.3,dt);[p.ry,p.vry]=sp(60,10,p.ry,p.vry,still?0:nx*Math.min(.3,60/b.width),dt);
      p.g.position.set(cx-cb.left-cw/2,-(cy-cb.top-ch/2)+p.l,0);p.g.rotation.set(p.rx,p.ry,0);p.g.scale.set(1+p.sq*.4,1-p.sq,1-p.sq);
      p.el.style.transform=`translateY(${(-p.l).toFixed(2)}px) scale(${(1+p.sq*.3).toFixed(3)},${(1-p.sq*.6).toFixed(3)})`}
    r.render(scene,cam)})(last);
  size();
}
const go=()=>groups.forEach(setup);
document.fonts?document.fonts.ready.then(go):go();
