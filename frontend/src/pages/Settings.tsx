import { useEffect, useState } from 'react';
import { getKeywords, createKeyword, deleteKeyword } from '../lib/api';
import type { Keyword } from '../lib/types';
import { useToast } from '../components/Toast';

export default function Settings() {
  const { toast } = useToast();
  const [keywords, setKeywords] = useState<Keyword[]>([]);
  const [newWord, setNewWord] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => { document.title = '키워드 관리 | LawNGood'; }, []);

  const fetchKeywords = async () => {
    const data = await getKeywords();
    setKeywords(data);
  };

  useEffect(() => { fetchKeywords(); }, []);

  const handleAdd = async () => {
    if (!newWord.trim()) return;
    setLoading(true);
    try {
      await createKeyword(newWord.trim());
      setNewWord('');
      await fetchKeywords();
      toast('키워드가 추가되었습니다.');
    } catch {
      toast('키워드 추가에 실패했습니다.', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!window.confirm('정말 삭제하시겠습니까?')) return;
    try {
      await deleteKeyword(id);
      await fetchKeywords();
      toast('키워드가 삭제되었습니다.', 'info');
    } catch {
      toast('삭제에 실패했습니다.', 'error');
    }
  };

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">키워드 관리</h1>

      <div className="bg-white rounded-xl border border-border p-6">
        <h2 className="text-sm font-semibold mb-4">수집 키워드 관리</h2>
        <p className="text-xs text-gray-500 mb-4">뉴스 크롤링에 사용되는 검색 키워드를 관리합니다.</p>

        <div className="flex flex-wrap gap-2 mb-4">
          {keywords.map((kw) => (
            <span
              key={kw.id}
              className="inline-flex items-center gap-1.5 bg-navy text-white text-sm px-3 py-1.5 rounded-full"
            >
              {kw.word}
              <button
                onClick={() => handleDelete(kw.id)}
                className="text-gray-300 hover:text-white text-xs ml-1"
              >
                ✕
              </button>
            </span>
          ))}
          {keywords.length === 0 && (
            <span className="text-gray-400 text-sm">등록된 키워드가 없습니다</span>
          )}
        </div>

        <div className="flex gap-2">
          <input
            type="text"
            placeholder="새 키워드 입력"
            value={newWord}
            onChange={(e) => setNewWord(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
            className="border rounded px-3 py-1.5 text-sm flex-1"
          />
          <button
            onClick={handleAdd}
            disabled={loading}
            className="bg-gold text-white text-sm px-4 py-1.5 rounded hover:opacity-90 disabled:opacity-50"
          >
            + 추가
          </button>
        </div>
      </div>
    </div>
  );
}
