use std::env;
use std::io::{BufRead, BufReader, Write};
use std::net::{TcpListener, TcpStream};
use std::thread;

fn respond(mut stream: TcpStream, greeting: &str) {
    let mut request_line = String::new();
    {
        let mut reader = BufReader::new(&stream);
        if reader.read_line(&mut request_line).is_err() {
            return;
        }
    }

    let path = request_line.split_whitespace().nth(1).unwrap_or("/");
    let body = match path {
        "/healthz" => "ok\n".to_string(),
        _ => format!("hello, {greeting}\n"),
    };

    let response = format!(
        "HTTP/1.1 200 OK\r\n\
         Content-Type: text/plain; charset=utf-8\r\n\
         Content-Length: {}\r\n\
         Connection: close\r\n\
         \r\n\
         {}",
        body.len(),
        body
    );

    let _ = stream.write_all(response.as_bytes());
    let _ = stream.flush();
}

fn main() {
    let port = env::var("PORT").unwrap_or_else(|_| String::from("8080"));
    let greeting = env::var("GREETING_NAME").unwrap_or_else(|_| String::from("world"));

    let listener = TcpListener::bind(format!("0.0.0.0:{port}"))
        .unwrap_or_else(|err| panic!("failed to bind 0.0.0.0:{port}: {err}"));

    println!("greeterd listening on 0.0.0.0:{port}");

    for stream in listener.incoming() {
        match stream {
            Ok(stream) => {
                let greeting = greeting.clone();
                thread::spawn(move || respond(stream, &greeting));
            }
            Err(err) => eprintln!("connection error: {err}"),
        }
    }
}
