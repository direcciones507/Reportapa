/* Pure helpers: no requests, bots or automatic sending. */
(function(root){
  const states={pendiente_confirmar:'Pendiente de confirmar',sin_ayuda:'Sin ayuda recibida',parcial:'Ayuda parcial',completa:'Ayuda completa'};
  function whatsappUrl(raw,reportId){
    if(typeof reportId!=='string'||!/^RPA-\d+$/.test(reportId))throw Error('El número de reporte no es válido. No se puede abrir WhatsApp.');
    const message='Hola, le escribimos de ReportaPA para dar seguimiento a su situación.\n\nNúmero de reporte: '+reportId+'\n\n¿Nos puede confirmar si ya recibió ayuda?\n\nGracias por su respuesta.';
    const value=String(raw||'').trim();
    if(!/^\+?[\d\s().-]+$/.test(value))throw Error('El teléfono registrado no es válido. No se puede abrir WhatsApp.');
    let phone=value.replace(/\D/g,'');
    if(phone.startsWith('507') && (phone.length===10||phone.length===11))phone=phone.slice(3);
    if(!/^(?:[2-5]\d{6}|[2-9]\d{7})$/.test(phone))throw Error('El teléfono registrado no es válido para Panamá. No se puede abrir WhatsApp.');
    return 'https://wa.me/507'+phone+'?text='+encodeURIComponent(message);
  }
  const helpers={states,whatsappUrl};
  if(typeof module!=='undefined'&&module.exports)module.exports=helpers;else root.ReportaFollowup=helpers;
})(globalThis);
