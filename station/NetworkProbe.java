// SPDX-License-Identifier: MIT
// Diagnose the same UID-based route as the music app. No TLS checks are disabled.
import android.system.Os;
import java.net.URL;
import javax.net.ssl.HttpsURLConnection;
import java.util.Arrays;
public final class NetworkProbe {
 public static void main(String[] args) throws Exception {
  Thread deadline=new Thread(() -> {try{Thread.sleep(15000);}catch(InterruptedException ignored){}System.err.println("PROBE_TIMEOUT");System.exit(124);});
  deadline.setDaemon(true);deadline.start();
  if(args.length!=2)throw new IllegalArgumentException("UID URL required");
  int uid=Integer.parseInt(args[0]);URL url=new URL(args[1]);
  if(uid<1000||uid>=100000||!url.getProtocol().equals("https")||!Arrays.asList("music.youtube.com","www.youtube.com","www.google.com","api.ipify.org").contains(url.getHost())||url.getUserInfo()!=null)throw new IllegalArgumentException("Unsupported probe");
  Os.setgid(3003);Os.setuid(uid);
  HttpsURLConnection c=(HttpsURLConnection)url.openConnection();
  c.setConnectTimeout(7000);c.setReadTimeout(7000);c.setInstanceFollowRedirects(false);c.setRequestProperty("User-Agent","MaxWave-Diagnostics/0.1");
  try{
   int code=c.getResponseCode();System.out.println("UID="+Os.getuid()+" HOST="+url.getHost()+" HTTP="+code);
   if(url.getHost().equals("api.ipify.org")&&code==200){byte[] data=new byte[80];int n=c.getInputStream().read(data);if(n>0)System.out.println("PUBLIC_IP="+new String(data,0,n,"UTF-8").trim());}
  }finally{c.disconnect();}
 }
}
