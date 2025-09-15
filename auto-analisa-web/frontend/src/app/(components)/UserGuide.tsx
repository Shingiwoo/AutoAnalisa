"use client"

export default function UserGuide(){
  return (
    <section className="rounded-2xl ring-1 ring-zinc-200 dark:ring-white/10 bg-white dark:bg-zinc-900 p-4 text-sm">
      <div className="font-semibold mb-1">Panduan Pengguna</div>
      <ul className="list-disc pl-5 space-y-1">
        <li>Tambah simbol di Watchlist lalu klik <b>Analisa</b> untuk membuat kartu analisa (maks 4 aktif).</li>
        <li>PlanCard menampilkan rencana <b>SPOT II</b> (Rules). Klik <b>Update</b> untuk penyegaran. Jika harga tembus <b>invalid</b>, sistem membuat versi baru dan memberi tanda <b>Updated</b>.</li>
        <li><b>LLM Verifikasi</b> opsional: klik <b>Tanya GPT</b> untuk verifikasi SPOT II; gunakan <b>Pratinjau (ghost)</b> untuk melihat overlay saran; <b>Terapkan Saran</b> untuk menyimpan.</li>
        <li><b>Chart</b>: garis Entry, TP, Invalid, S/R akan tampil. Ghost overlay ditampilkan dengan garis putus-putus.</li>
        <li><b>Macro Harian</b> dan <b>Sessions Hint</b>: ringkasan makro dan jam WIB signifikan tampil otomatis bila tersedia.</li>
        <li><b>Aturan</b>: Edukasi, bukan saran finansial. Terdapat rate-limit dan batas harian LLM per pengguna.</li>
      </ul>
    </section>
  )
}

