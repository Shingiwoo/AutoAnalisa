"use client"
import { useEffect, useState } from "react"
import SiteHeader from "./SiteHeader"

export default function TopNav(){
  const [loggedIn,setLoggedIn]=useState(false)
  const [isAdmin,setIsAdmin]=useState(false)
  useEffect(()=>{
    if(typeof window!=='undefined'){
      setLoggedIn(!!(localStorage.getItem('token')||localStorage.getItem('access_token')))
      setIsAdmin(localStorage.getItem('role')==='admin')
    }
  },[])
  return <SiteHeader loggedIn={loggedIn} isAdmin={isAdmin} />
}

