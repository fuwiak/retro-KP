import * as THREE from 'three';

let renderer, scene, camera, mesh;
init();
animate();

function init() {
  const canvas = document.getElementById('bg');
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setSize(window.innerWidth, window.innerHeight);

  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(55, window.innerWidth / window.innerHeight, 0.1, 300);
  camera.position.set(0, 6, 10);
  camera.lookAt(0, 0, 0);

  // geometry wireframe
  const geom = new THREE.PlaneGeometry(200, 200, 200, 200);
  geom.rotateX(-Math.PI / 2);
  const mat = new THREE.ShaderMaterial({
    uniforms: { uTime: { value: 0 } },
    vertexShader: `
      uniform float uTime;
      void main() {
        vec3 p = position;
        p.y += (sin(p.x*0.25 + uTime*1.5) + cos(p.z*0.35 - uTime*1.2))*0.15;
        p.z += uTime*2.0;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(p,1.0);
      }`,
    fragmentShader: `void main(){ gl_FragColor = vec4(0.0,1.0,0.4,1.0); }`,
    wireframe: true
  });
  mesh = new THREE.Mesh(geom, mat);
  scene.add(mesh);

  window.addEventListener('resize', onResize);
}

function onResize() {
  const w = window.innerWidth, h = window.innerHeight;
  renderer.setSize(w, h);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}

let last = performance.now();
function animate(now) {
  const dt = (now - last) / 1000;
  last = now;
  mesh.material.uniforms.uTime.value += dt * 1.5;
  renderer.render(scene, camera);
  requestAnimationFrame(animate);
}
