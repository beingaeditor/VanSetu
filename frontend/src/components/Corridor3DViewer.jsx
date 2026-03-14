import { Canvas } from "@react-three/fiber";

function Tree({ position }) {
  return (
    <mesh position={position}>
      <cylinderGeometry args={[0.2,0.2,2]} />
      <meshStandardMaterial color="brown"/>
    </mesh>
  );
}

function Road() {
  return (
    <mesh position={[0,0,0]}>
      <boxGeometry args={[20,0.2,6]}/>
      <meshStandardMaterial color="#555"/>
    </mesh>
  );
}

function CorridorScene({ type }) {

  return (
    <>
      <ambientLight intensity={0.6}/>
      <directionalLight position={[5,10,5]}/>

      <Road/>

      {/* Trees */}

      {type === "tree_corridor" && (
        <>
          <Tree position={[-5,1,2]}/>
          <Tree position={[5,1,2]}/>
        </>
      )}

      {type === "shade_corridor" && (
        <>
          <Tree position={[-6,1,2]}/>
          <Tree position={[6,1,2]}/>
          <mesh position={[0,2,0]}>
            <boxGeometry args={[10,0.2,4]}/>
            <meshStandardMaterial color="green"/>
          </mesh>
        </>
      )}

      {type === "green_mobility_corridor" && (
        <>
          <Tree position={[-8,1,2]}/>
          <Tree position={[8,1,2]}/>
          <mesh position={[0,0.1,2]}>
            <boxGeometry args={[20,0.1,2]}/>
            <meshStandardMaterial color="green"/>
          </mesh>
        </>
      )}
    </>
  );
}

export default function Corridor3DViewer({ type }) {

  return (
    <div style={{height:"400px"}}>

      <Canvas camera={{position:[0,8,20]}}>
        <CorridorScene type={type}/>
      </Canvas>

    </div>
  );
}