import './App.css'
import useFetch from './hooks/useFetch';
import Chatbot from './components/chatbot/chatbot';

function App() {
  const { data, loading, error } = useFetch('agents');
  console.log(data, loading, error);

  return (
    <div>
      <Chatbot />
    </div>
  )
}

export default App
